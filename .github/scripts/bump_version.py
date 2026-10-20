import re
import subprocess
import sys


def get_latest_tag():
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
        tags = result.stdout.strip().split("\n")
        return tags[0] if tags and tags[0] else None
    except Exception:
        return None


def parse_version(v_str):
    core = v_str.split("-")[0]
    parts = list(map(int, core.split(".")))
    while len(parts) < 3:
        parts.append(0)

    is_beta = "-" in v_str and "beta" in v_str
    beta_num = -1
    if is_beta:
        match = re.search(r"beta\.(\d+)", v_str)
        if match:
            beta_num = int(match.group(1))

    return parts[0], parts[1], parts[2], is_beta, beta_num


def bump_version(current, bump_type, release_status, all_tags=None):
    is_target_beta = release_status == "beta"

    if not current:
        if is_target_beta:
            return "1.0.0-beta.0"
        return "1.0.0"

    major, minor, patch, is_curr_beta, curr_beta_num = parse_version(current)

    latest_stable = (0, 0, 0)
    if all_tags:
        for t in all_tags:
            t = t.lstrip("v")
            if t and "-" not in t:
                s_major, s_minor, s_patch, _, _ = parse_version(t)
                latest_stable = (s_major, s_minor, s_patch)
                break
    else:
        try:
            res = subprocess.run(
                ["git", "tag", "--list", "--sort=-v:refname"],
                capture_output=True,
                text=True,
            )
            for t in res.stdout.strip().split("\n"):
                t = t.lstrip("v")
                if t and "-" not in t:
                    s_major, s_minor, s_patch, _, _ = parse_version(t)
                    latest_stable = (s_major, s_minor, s_patch)
                    break
        except Exception:
            pass

    if bump_type == "major":
        target_core = (latest_stable[0] + 1, 0, 0)
    elif bump_type == "minor":
        target_core = (latest_stable[0], latest_stable[1] + 1, 0)
    else:
        target_core = (latest_stable[0], latest_stable[1], latest_stable[2] + 1)

    target_core_str = f"{target_core[0]}.{target_core[1]}.{target_core[2]}"

    if is_target_beta:
        current_core = (major, minor, patch)
        if current_core == target_core and is_curr_beta:
            return f"{target_core_str}-beta.{curr_beta_num + 1}"
        return f"{target_core_str}-beta.0"

    current_core = (major, minor, patch)
    if current_core == target_core and is_curr_beta:
        return target_core_str

    return target_core_str


def main():
    if len(sys.argv) < 3:
        print("Usage: bump_version.py <bump_type> <release_status>")
        sys.exit(1)
    bump_type = sys.argv[1]
    release_status = sys.argv[2]
    current = get_latest_tag()
    new_version = bump_version(current, bump_type, release_status)
    print(new_version)


if __name__ == "__main__":
    main()
