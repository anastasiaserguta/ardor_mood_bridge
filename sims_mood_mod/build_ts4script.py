from pathlib import Path
from zipfile import ZIP_STORED, ZipFile


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT / "ArdorMood.ts4script"


def main():
    with ZipFile(OUT, "w", ZIP_STORED) as archive:
        archive.write(SRC / "ardor_mood.py", "ardor_mood/__init__.py")

    print(OUT)


if __name__ == "__main__":
    main()
