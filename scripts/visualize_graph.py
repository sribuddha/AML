"""Visualize the AML_Workflow LangGraph as Mermaid (and PNG if available)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in [ROOT, ROOT / "src"]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def main():
    from src.aml_workflow.graph import create_workflow

    # graph construction doesn't invoke nodes, so a mock db suffices
    app = create_workflow(db=object())

    mermaid = app.get_graph().draw_mermaid()
    print(mermaid)

    out = Path(__file__).resolve().parent / "workflow.mermaid"
    out.write_text(mermaid)
    print(f"\nSaved to {out}")

    try:
        png = app.get_graph().draw_mermaid_png()
        png_path = out.with_suffix(".png")
        png_path.write_bytes(png)
        print(f"Saved to {png_path}")
    except Exception:
        print("PNG export requires pygraphviz + Graphviz — skipping")


if __name__ == "__main__":
    main()
