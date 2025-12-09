import sys
from pathlib import Path
from backend.legacy.services.markdown_llm import preprocess_markdown_for_bbox

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_preprocess_markdown.py <input_markdown_file>")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)
    markdown_text = input_path.read_text(encoding="utf-8")
    processed = preprocess_markdown_for_bbox(markdown_text)
    print(processed)

if __name__ == "__main__":
    main()
