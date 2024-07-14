from cx_Freeze import setup, Executable

# Define the executable
executable = Executable(
    script="project.py",  # Ensure this matches your script name
    base="Win32GUI",  # Use "Win32GUI" for a GUI app, set to None for console app
    target_name="inmate_details.exe",
    icon=None  # Path to the icon file if you have one
)

# Define the setup
setup(
    name="Inmate Details",
    version="1.0",
    description="Fetch and display inmate details",
    executables=[executable],
    options={
        "build_exe": {
            "packages": ["requests", "bs4", "pymongo", "tkinter"],
            "include_files": [],  # List of additional files to include
            "excludes": ["config"],  # Exclude the config.py file
        }
    }
)
