import argparse
import asyncio

from sqlalchemy import select

from src.bff.database import async_session_factory
from src.file_processor.models import UploadedFiles
from src.file_processor.service import retry_upload


async def retry(upload_id: str) -> None:
    async with async_session_factory() as session:
        upload = await session.get(UploadedFiles, upload_id)
        if upload is None:
            print(f"ERROR: Upload {upload_id} not found")
            return

        result = await retry_upload(upload_id, session)
        print(f"Retry complete — new upload_id: {result['upload_id']}")
        print(f"  Filename:       {result['filename']}")
        print(f"  Rows inserted:  {result['accepted_count']}")


def main():
    parser = argparse.ArgumentParser(description="Retry a failed upload")
    parser.add_argument("upload_id", help="ID of the failed upload to retry")
    args = parser.parse_args()
    asyncio.run(retry(args.upload_id))


if __name__ == "__main__":
    main()
