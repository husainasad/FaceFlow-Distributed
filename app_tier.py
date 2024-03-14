from Resources.model.face_recognition import face_match
import boto3, base64, json, asyncio, os

with open('config.json') as f:
    config = json.load(f)

AWS_REGION = config['AWS_REGION']
REQUEST_QUEUE_URL = config['REQUEST_QUEUE_URL']
RESPONSE_QUEUE_URL = config['RESPONSE_QUEUE_URL']
IN_BUCKET = config['IN_BUCKET']
OUT_BUCKET = config['OUT_BUCKET']
DATA_PT_PATH = config['DATA_PT_PATH']

sts_client = boto3.client('sts')

session = boto3.Session()

sqs_client = session.client('sqs', region_name=AWS_REGION)

s3_client = session.client('s3')

data_pt_path = './Resources/model/data.pt'

async def process_img(image_data):
    try:
        with open('temp.jpg', 'wb') as f:
            f.write(image_data)
        result = face_match('temp.jpg', DATA_PT_PATH)[0]
        return f'{result}'
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        os.remove('temp.jpg')
    

async def process_msg():
    while True:
        receive_response = sqs_client.receive_message(
            QueueUrl=REQUEST_QUEUE_URL,
            AttributeNames=[
                'SentTimestamp'
            ],
            MaxNumberOfMessages=1,
            MessageAttributeNames=[
                'All'
            ],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )

        if 'Messages' in receive_response:
            message = receive_response['Messages'][0]
            
            message_body = json.loads(message['Body'])

            image_name = message_body['image_name']
            # print('image name is: ' + image_name)

            image_encoded = message_body['image_encoded']
            image_data = base64.b64decode(image_encoded)

            # print('Received image data from SQS')

            model_result = await process_img(image_data)

            # Add request and response in S3 buckets
            s3_client.put_object(Body=image_data, Bucket=IN_BUCKET, Key=image_name + '.jpg')
            s3_client.put_object(Body=model_result, Bucket=OUT_BUCKET, Key=image_name)

            # Delete received message from queue
            receipt_handle = message['ReceiptHandle']
            sqs_client.delete_message(
                QueueUrl=REQUEST_QUEUE_URL,
                ReceiptHandle=receipt_handle
            )
            # print('Deleted message')
            
            output_msg = f'{image_name}:{model_result}'
            # print(output_msg)

            sqs_client.send_message(
                QueueUrl=RESPONSE_QUEUE_URL,
                MessageBody=(
                    output_msg
                )
            )

            # print(f"Message sent to Response SQS with MessageId: {send_response['MessageId']}")


if __name__ == "__main__":
    # process_msg()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(process_msg())