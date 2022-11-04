# -*- coding: utf-8 -*-
import boto3
from cfn_custom_resource import CfnCustomResource
import logging


custom_resource = CfnCustomResource(__name__)
logger = logging.getLogger(__name__)
s3 = boto3.resource('s3')


@custom_resource.on(request_type=custom_resource.DELETE)
def empty_bucket(event, context, cfn_response, *, delete_batch_size=1000):
    bucket_name = event['ResourceProperties']['BucketName']
    bucket = s3.Bucket(bucket_name)
    objects_to_delete = [{'Key': _.key, 'VersionId': _.version_id} for _ in bucket.object_versions.all()]
    logger.info('Emptying %d object versions from bucket %s', len(objects_to_delete), bucket_name)
    error_count = 0
    while objects_to_delete:
        delete_outcome = bucket.delete_objects(Delete={'Objects': objects_to_delete[:delete_batch_size], 'Quiet': True})
        error_list = delete_outcome.get('Errors') or []
        error_count += len(error_list)
        for error in error_list:
            logger.warning('Failed to delete s3://%s/%s(%s): (%s) %s', bucket_name, error.get('Key'), error.get('VersionId'), error.get('Code'), error.get('Message'))
        objects_to_delete = objects_to_delete[delete_batch_size:]
    if error_count == 0:
        logger.info('Done emptying bucket %s', bucket_name)
    else:
        logger.warning('Failed to delete %d object versions from bucket %s', error_count, bucket_name)
