import json
import re
import sys
from datetime import datetime
import urllib.error
import urllib.request

# PEP 508 requirement matching (package name, operator, version)
REQUIREMENT_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(==|===|~=|>=|<=|>|<)?\s*([A-Za-z0-9_.\-+*]*)"
)


def parse_line(line: str):
    """Strip comments/flags and extract (package, operator, version)."""
    clean_line = line.split("#")[0].strip()
    if not clean_line or clean_line.startswith(("-", "--")):
        return None, None, None

    match = REQUIREMENT_RE.match(clean_line)
    if not match:
        return None, None, None

    pkg, op, ver = match.groups()
    return pkg, op, ver if ver else None


def fetch_pypi(path: str):
    """Query https://pypi.org/pypi/<path>/json and return (status_code, data)."""
    url = f"https://pypi.org/pypi/{path}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "PyPIChecker/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, None
    except Exception as err:
        print(f"Warning: Network failure for {url}: {err}", file=sys.stderr)
        return None, None


def check_file(filepath: str):
    checked_count = 0
    missing_packages_count = 0
    missing_versions_count = 0

    # Store: (datetime_obj, formatted_label)
    oldest_pinned = None

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        pkg, op, ver = parse_line(line)
        if not pkg:
            continue

        checked_count += 1

        # 1. Check package presence at pypi/<name>/json
        pkg_code, _ = fetch_pypi(pkg)
        if pkg_code == 404:
            missing_packages_count += 1
            continue
        elif pkg_code != 200:
            continue

        # 2. Check release presence at pypi/<name>/<version>/json
        if ver:
            ver_code, ver_data = fetch_pypi(f"{pkg}/{ver}")
            if ver_code == 404:
                missing_versions_count += 1
            elif ver_code == 200 and ver_data:
                # Use upload_time of the first file under 'urls'
                urls = ver_data.get("urls", [])
                if urls and "upload_time" in urls[0]:
                    upload_str = urls[0]["upload_time"]
                    dt = datetime.fromisoformat(upload_str)
                    label = f"{pkg}=={ver}({dt.year})"

                    if oldest_pinned is None or dt < oldest_pinned[0]:
                        oldest_pinned = (dt, label)

    print(f"Dependencies checked: {checked_count}")
    print(f"Packages not on PyPi: {missing_packages_count}")
    print(f"Versions not on PyPI: {missing_versions_count}")
    print(f"Oldest pinned release: {oldest_pinned[1] if oldest_pinned else 'None'}")


if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    check_file(target_file)