# -*- coding: utf-8 -*-
import logging
import os
import requests
import typing


__all__ = (
    'CfnCustomResource',
    'CfnResponse',
)


logger = logging.getLogger(__name__)


class CfnCustomResource:

    CREATE = 'Create'
    DELETE = 'Delete'
    UPDATE = 'Update'

    def __init__(self, module_name, *, default_log_level='INFO'):
        self.handlers = {}
        logging.getLogger(module_name).setLevel(os.environ.get('LOG_LEVEL') or default_log_level)

    def __call__(self, event, context):
        with CfnResponse(event, context) as cfn_response:
            request_type = event.get('RequestType')
            handler_fn = self.handlers.get(request_type)
            if handler_fn:
                data = handler_fn(event, context, cfn_response)
                cfn_response.send_success(data=data)

    def on(self, request_type):
        def register(fn):
            self.handlers[request_type] = fn
        return register


class CfnResponse:

    def __init__(self, event, context, *, physical_resource_id: typing.Optional[str] = None, no_echo: bool = False, data: typing.Optional[dict] = None):
        self.event = event
        self.context = context
        self.physical_resource_id: str = physical_resource_id or self.logical_resource_id
        self.no_echo: bool = no_echo
        self.data: dict = dict() if data is None else data
        self.sent = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.sent:
            if exc_type is None and exc_val is None:
                self.send_success()
            else:
                self.send_failed(f'{exc_type.__name__}: {exc_val}')

    @property
    def logical_resource_id(self):
        return self.event['LogicalResourceId']

    @property
    def request_id(self):
        return self.event['RequestId']

    @property
    def stack_id(self):
        return self.event['StackId']

    def send_success(self, *, physical_resource_id : typing.Optional[str] = None, data : typing.Optional[dict] = None):
        if data is not None:
            self.data = data
        if physical_resource_id is not None:
            self.physical_resource_id = physical_resource_id
        logger.info('Sending success for %s in stack %s', self.logical_resource_id, self.stack_id)
        self._send('SUCCESS')

    def send_failed(self, reason : typing.Optional[str] = None):
        if not reason:
            reason = f'See the details in CloudWatch Log Stream: {self.context.log_stream_name}'
        logger.error('Sending FAILED for %s in stack %s: %s', self.logical_resource_id, self.stack_id, reason)
        self._send('FAILED', {'Reason': reason})

    def _send(self, status: str, response_object: typing.Optional[dict] = None):
        response_object = {
            **(dict() if response_object is None else response_object),
            'Status': status,
            'PhysicalResourceId': self.physical_resource_id,
            'StackId': self.stack_id,
            'RequestId': self.request_id,
            'LogicalResourceId': self.logical_resource_id,
            'NoEcho': self.no_echo,
            'Data': self.data,
        }
        response_url = self.event['ResponseURL']
        logger.debug('PUT %s: %r', response_url, response_object)
        if response_url != 'http://pre-signed-S3-url-for-response':
            requests.put(response_url, json=response_object)
        self.sent = True
