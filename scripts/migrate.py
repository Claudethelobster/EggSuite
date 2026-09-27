import os
import shutil

# 1. Define the exact file movements
moves = {
    "badger_loop_py3_3.py": "external_modules/badger_loop_py3_3.py",
    "core/theme.py": "ui/theme.py",
    "core/plot_worker.py": "apps/plot_and_stats/plot_worker.py",
    "ui/main_window.py": "apps/plot_and_stats/main_window.py",
    "ui/dialogs/analysis.py": "apps/plot_and_stats/analysis.py",
    "ui/dialogs/analysis_3d.py": "apps/plot_and_stats/analysis_3d.py",
    "ui/dialogs/analysis_hist.py": "apps/plot_and_stats/analysis_hist.py",
    "ui/dialogs/fitting.py": "apps/plot_and_stats/fitting.py",
    "ui/dialogs/fitting_3d.py": "apps/plot_and_stats/fitting_3d.py",
    "ui/dialogs/settings.py": "apps/settings/settings.py",
}

# Entire directories to move
dir_moves = {
    "ui/renderers": "apps/plot_and_stats/renderers"
}

# 2. Define the exact text replacements for the import paths
replacements = {
    "core.theme": "ui.theme",
    "core.plot_worker": "apps.plot_and_stats.plot_worker",
    "ui.main_window": "apps.plot_and_stats.main_window",
    "ui.dialogs.analysis": "apps.plot_and_stats.analysis",
    "ui.dialogs.analysis_3d": "apps.plot_and_stats.analysis_3d",
    "ui.dialogs.analysis_hist": "apps.plot_and_stats.analysis_hist",
    "ui.dialogs.fitting": "apps.plot_and_stats.fitting",
    "ui.dialogs.fitting_3d": "apps.plot_and_stats.fitting_3d",
    "ui.dialogs.settings": "apps.settings.settings",
    "ui.renderers": "apps.plot_and_stats.renderers",
    "import badger_loop_py3_3": "from external_modules import badger_loop_py3_3"
}

def main():
    print("🚀 Starting EggSuite Migration...\n")
    
    # A. Create necessary directories
    directories = [
        "external_modules",
        "apps/hub",
        "apps/plot_and_stats",
        "apps/settings"
    ]
    for d in directories:
        os.makedirs(d, exist_ok=True)
        # Create an __init__.py in every new folder to make them Python modules
        open(os.path.join(d, "__init__.py"), 'a').close()
        print(f"Created directory: {d}")

    # Create root apps __init__.py
    open("apps/__init__.py", 'a').close()

    print("\n📦 Moving files...")
    # B. Move individual files
    for src, dest in moves.items():
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)
            print(f"  Moved: {src} -> {dest}")
        else:
            print(f"  Skipped (Not Found): {src}")

    # C. Move directories
    for src, dest in dir_moves.items():
        if os.path.exists(src):
            shutil.move(src, dest)
            print(f"  Moved Directory: {src} -> {dest}")
            
    print("\n🔗 Rewriting Import Paths...")
    # D. Search all .py files and rewrite the imports
    py_files = []
    for root, _, files in os.walk("."):
        # Don't modify the migration script itself or virtual environments
        if "venv" in root or ".env" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py") and file != "migrate.py":
                py_files.append(os.path.join(root, file))

    updated_count = 0
    for file_path in py_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = content
        for old_import, new_import in replacements.items():
            new_content = new_content.replace(old_import, new_import)

        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            updated_count += 1

    print(f"  Updated imports in {updated_count} files.")
    
    # E. Cleanup old __main__.py if it exists
    if os.path.exists("__main__.py"):
        os.rename("__main__.py", "main.py")
        print("\n✨ Renamed __main__.py to main.py")

    print("\n✅ Migration Complete! Welcome to EggSuite.")

if __name__ == "__main__":
    main()