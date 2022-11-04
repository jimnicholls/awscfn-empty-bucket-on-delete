# -*- coding: utf-8 -*-
import boto3
from cfn_response import CfnResponse
import logging
import os


logger = logging.getLogger('empty_bucket_on_delete.lambda_handler')
s3 = boto3.resource('s3')


def handler(event, context):
    logging.getLogger('empty_bucket_on_delete').setLevel(os.environ.get('DEFAULT_LOG_LEVEL', 'INFO'))
    with CfnResponse(event, context) as cfn_response:
        cfn_response.physical_resource_id = cfn_response.logical_resource_id
        request_type = event.get('RequestType')
        try:
            bucket_name = event['ResourceProperties']['BucketName']
        except KeyError:
            bucket_name = os.environ['BUCKET_NAME']
        logger.debug('%r', {
            'request_type': request_type,
            'stack_id': cfn_response.stack_id,
            'request_id': cfn_response.request_id,
            'logical_resource_id': cfn_response.logical_resource_id,
            'bucket_name': bucket_name,
        })
        if request_type == 'Delete':
            empty_bucket(bucket_name)


def empty_bucket(bucket_name, *, delete_batch_size=1000):
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
