"""Vega CLI 入口。

用法:
  vega ingest <doc_id> --file <path> --plugin novel --workdir <dir>
  vega profile <doc_id> --entity <name> --workdir <dir>   # 未实现(后续)
  vega query <doc_id> "问题" --workdir <dir>              # 未实现(后续)
"""

from __future__ import annotations

import argparse
import asyncio
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

    p_profile = sub.add_parser("profile", help="查实体画像(未实现)")
    p_profile.add_argument("doc_id")
    p_profile.add_argument("--entity", required=True)
    p_profile.add_argument("--workdir", default="./vega-workspace")

    p_query = sub.add_parser("query", help="问答检索(未实现)")
    p_query.add_argument("doc_id")
    p_query.add_argument("question")
    p_query.add_argument("--workdir", default="./vega-workspace")

    args = parser.parse_args(argv)

    if args.cmd == "ingest":
        return asyncio.run(_ingest(args))
    print(f"[vega] {args.cmd} —— 尚未实现", file=sys.stderr)
    return 0


async def _ingest(args: argparse.Namespace) -> int:
    from pathlib import Path

    from vega.core.ingest import ingest_document
    from vega.plugins.novel import NovelPlugin

    if args.plugin != "novel":
        print(f"[vega] 暂不支持插件:{args.plugin}(仅 novel)", file=sys.stderr)
        return 1
    text = Path(args.file).read_text(encoding="utf-8")
    await ingest_document(
        args.doc_id, text, NovelPlugin(), workdir=args.workdir, resume=args.resume
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
