import os
import sys

def update_wsl_conf():
    path = "/etc/wsl.conf"
    if os.path.exists(path):
        with open(path, "r") as f:
            content = f.read()
    else:
        content = ""

    if "[automount]" not in content:
        content = content.strip() + "\n\n[automount]\nmountFsTab=true\n"
    elif "mountFsTab" not in content:
        content = content.replace("[automount]", "[automount]\nmountFsTab=true")
    
    with open(path, "w") as f:
        f.write(content.strip() + "\n")
    print("Updated /etc/wsl.conf:")
    print(content.strip())

def update_fstab():
    path = "/etc/fstab"
    target_entry = "tmpfs /mnt/shared_memory tmpfs defaults 0 0\n"
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.readlines()
    else:
        lines = []

    new_lines = []
    found = False
    for line in lines:
        if "/mnt/shared_memory" in line:
            new_lines.append(target_entry)
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(target_entry)

    with open(path, "w") as f:
        f.writelines(new_lines)
    print("\nUpdated /etc/fstab:")
    print("".join(new_lines).strip())

if __name__ == "__main__":
    os.makedirs("/mnt/shared_memory", exist_ok=True)
    update_wsl_conf()
    update_fstab()
