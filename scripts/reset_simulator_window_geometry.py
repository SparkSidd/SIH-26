import os

def reset_webots_geometry():
    path = os.path.expanduser("~/.config/Cyberbotics/Webots-R2025a.conf")
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        content = f.read()

    # Fix negative or offscreen coordinates
    lines = content.splitlines()
    new_lines = []
    in_main_window = False
    for line in lines:
        if line.strip() == "[MainWindow]":
            in_main_window = True
            new_lines.append(line)
            continue
        if in_main_window and line.startswith("["):
            in_main_window = False

        if in_main_window:
            if line.startswith("position="):
                new_lines.append("position=@Point(100 100)")
                continue
            if line.startswith("size="):
                new_lines.append("size=@Size(1280 800)")
                continue
            if line.startswith("maximized="):
                new_lines.append("maximized=false")
                continue
        new_lines.append(line)

    with open(path, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    print(f"Successfully calibrated window geometry in {path}")

if __name__ == "__main__":
    reset_webots_geometry()
