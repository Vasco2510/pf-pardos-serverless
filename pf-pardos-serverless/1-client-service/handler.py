import json
import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal

# Inicializamos DynamoDB
dynamodb = boto3.resource('dynamodb')
# Leemos el nombre de la tabla desde la variable de entorno (definida en serverless.yml)
ORDERS_TABLE = os.environ['ORDERS_TABLE_NAME']
table = dynamodb.Table(ORDERS_TABLE)

def create_order(event, context):
    try:
        print("Evento recibido:", event)
        body = json.loads(event.get('body', '{}'))

        # 1. Validación Básica
        tenant_id = body.get('tenantId') # Ej: "SEDE-MIRAFLORES"
        items = body.get('items')        # Ej: [{"id": "p1", "qty": 1}]
        
        if not tenant_id or not items:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Faltan datos: tenantId y items son obligatorios"})
            }

        # 2. Preparar el Item para DynamoDB
        order_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        item = {
            'tenantId': tenant_id,       # PK
            'orderId': order_id,         # SK
            'status': 'CREATED',         # Estado inicial
            'items': items,
            'createdAt': timestamp,
            'customerName': body.get('customerName', 'Cliente Anónimo')
        }

        # 3. Guardar en DynamoDB
        # Convertimos float a Decimal si es necesario, pero aquí items es lista
        table.put_item(Item=item)

        # 4. Respuesta Exitosa
        return {
            "statusCode": 201,
            "headers": {
                "Access-Control-Allow-Origin": "*", # CORS para frontend
            },
            "body": json.dumps({
                "message": "Pedido creado exitosamente",
                "orderId": order_id,
                "tenantId": tenant_id
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error interno del servidor", "details": str(e)})
        }