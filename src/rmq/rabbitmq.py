import aio_pika


async def create_rabbitmq_connection(
    RABBITMQ_URL: str, RABBITMQ_USER: str, RABBITMQ_PASS: str
) -> aio_pika.RobustConnection:
    connection = await aio_pika.connect_robust(
        RABBITMQ_URL,
        login=RABBITMQ_USER,
        password=RABBITMQ_PASS,
    )
    return connection

async def create_rabbitmq_channel(
    connection: aio_pika.RobustConnection,
) -> aio_pika.RobustChannel:
    channel = await connection.channel()
    return channel