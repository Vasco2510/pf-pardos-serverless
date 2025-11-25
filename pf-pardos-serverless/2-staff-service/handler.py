import json
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sfn = boto3.client('stepfunctions')
ORDERS_TABLE = os.environ['ORDERS_TABLE_NAME']
table = dynamodb.Table(ORDERS_TABLE)

# --- LAMBDA 1: Usada por Step Functions (Interna) ---
def manage_state(event, context):
    """
    Esta función se ejecuta al entrar a un estado (ej: COCINA).
    1. Recibe el Token de la Step Function.
    2. Actualiza el estado en DynamoDB.
    3. Guarda el Token para poder reanudar después.
    """
    print("SFN Event:", event)
    
    order_id = event.get('orderId')
    tenant_id = event.get('tenantId')
    new_status = event.get('status') # COOKING, PACKAGING, etc.
    task_token = event.get('taskToken') # El token de pausa
    
    if not task_token:
        print("ADVERTENCIA: No hay token de tarea. El flujo no se pausará correctamente.")

    # Actualizamos DynamoDB
    try:
        update_expr = "set #s = :s, lastUpdated = :t"
        expr_values = {
            ':s': new_status, 
            ':t': datetime.utcnow().isoformat()
        }
        
        # Si hay token, lo guardamos también
        if task_token:
            update_expr += ", taskToken = :tt"
            expr_values[':tt'] = task_token

        table.update_item(
            Key={'tenantId': tenant_id, 'orderId': order_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues=expr_values
        )
        print(f"Pedido {order_id} actualizado a {new_status}")
        
        # IMPORTANTE: No devolvemos nada especial, porque estamos en modo .waitForTaskToken
        # La Step Function ignorará este return y esperará hasta que alguien llame a SendTaskSuccess
        return {"status": "paused", "waitingFor": new_status}

    except Exception as e:
        print(f"Error actualizando DB: {str(e)}")
        raise e

# --- LAMBDA 2: Usada por el Staff (API Gateway) ---
def advance_order(event, context):
    """
    El cocinero dice: 'Terminé'.
    1. Buscamos el Token en la BD.
    2. Enviamos SendTaskSuccess a Step Functions.
    """
    try:
        body = json.loads(event.get('body', '{}'))
        order_id = body.get('orderId')
        tenant_id = body.get('tenantId')
        
        # 1. Obtener el Token actual de la BD
        response = table.get_item(Key={'tenantId': tenant_id, 'orderId': order_id})
        item = response.get('Item')
        
        if not item or 'taskToken' not in item:
            return {"statusCode": 400, "body": json.dumps({"error": "El pedido no está esperando acción o no existe"})}
            
        task_token = item['taskToken']
        
        # 2. Desbloquear la Step Function
        # Aquí es donde ocurre la magia: Le decimos a SFN "Continúa"
        sfn.send_task_success(
            taskToken=task_token,
            output=json.dumps({"message": "Avanzado por Staff", "previousStatus": item['status']})
        )
        
        return {
            "statusCode": 200, 
            "body": json.dumps({"message": "Flujo avanzado exitosamente"})
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}