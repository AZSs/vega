"""Vega CLI 入口。

用法(规划):
  vega ingest <doc_id> --file <path> --plugin novel --workdir <dir>
  vega profile <doc_id> --entity <name> --workdir <dir>
  vega query <doc_id> "问题" --workdir <dir>
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vega", description="把长文本织成知识图谱的通用引擎")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="ingest 一份长文本到知识库")
    p_ingest.add_argument("doc_id")
    p_ingest.add_argument("--file", required=True)
    p_ingest.add_argument("--plugin", default="novel")
    p_ingest.add_argument("--workdir", default="./vega-workspace")
    p_ingest.add_argument("--resume", action="store_true")

    p_profile = sub.add_parser("profile", help="查实体画像")
    p_profile.add_argument("doc_id")
    p_profile.add_argument("--entity", required=True)
    p_profile.add_argument("--workdir", default="./vega-workspace")

    p_query = sub.add_parser("query", help="问答检索")
    p_query.add_argument("doc_id")
    p_query.add_argument("question")
    p_query.add_argument("--workdir", default="./vega-workspace")

    args = parser.parse_args(argv)
    print(f"[vega] {args.cmd} —— 骨架阶段,尚未实现", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
