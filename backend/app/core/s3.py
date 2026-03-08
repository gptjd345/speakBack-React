import boto3
import uuid
from botocore.exceptions import ClientError
from app.core.config import settings

s3_client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)

BUCKET = settings.S3_BUCKET
PREFIX = "uploads/"


def generate_presigned_upload_url(original_filename: str, content_type: str = "audio/wav") -> dict:
    """
    프론트가 S3에 직접 PUT 업로드할 수 있는 Presigned URL 반환
    유효기간: 5분
    """
    ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "wav"
    s3_key = f"{PREFIX}{uuid.uuid4()}.{ext}"

    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=300,  # 5분
    )

    return {
        "upload_url": presigned_url,
        "s3_key": s3_key,
    }


def download_file_bytes(s3_key: str) -> bytes:
    """S3에서 파일 bytes 다운로드"""
    response = s3_client.get_object(Bucket=BUCKET, Key=s3_key)
    return response["Body"].read()


def delete_file(s3_key: str) -> None:
    """S3 파일 즉시 삭제 (분석 완료 후 호출)"""
    try:
        s3_client.delete_object(Bucket=BUCKET, Key=s3_key)
    except ClientError:
        pass  # 이미 삭제됐거나 없어도 무시