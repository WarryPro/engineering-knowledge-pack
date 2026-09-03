"""Two entry points currently call the same concrete service."""

from fulfillment_service import FulfillmentService


def checkout_handler(service: FulfillmentService, request_json: dict):
    return service.fulfill(request_json)


def warehouse_batch_row(service: FulfillmentService, row: dict):
    # warehouse rows use the same shape today
    return service.fulfill(
        {"order_id": row["order_id"], "sku": row["sku"], "qty": row["qty"]}
    )
