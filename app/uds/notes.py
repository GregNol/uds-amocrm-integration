"""Сборка текста служебного примечания в сделку amoCRM из payload UDS."""

_ORDER_LINK = "https://admin.getuds.app/admin/orders?order={order_id}"
_CUSTOMER_LINK = "https://admin.getuds.app/admin/customers/{customer_id}/info"

_SEP = "-" * 64
_HR = "=" * 32

_UNITS = {
    "PIECE": "шт.",
    "HOUR": "ч.",
    "KG": "кг",
    "GRAM": "г",
    "LITER": "л",
    "METER": "м",
}

_DELIVERY_TYPE = {"PICKUP": "Самовывоз", "COURIER": "Доставка курьером"}


def _money(value) -> str:
    """3400.0 -> '3 400 руб.' (без копеек, если целое)."""
    try:
        num = float(value or 0)
    except (TypeError, ValueError):
        return f"{value} руб."
    text = f"{num:,.0f}" if num == int(num) else f"{num:,.2f}"
    return text.replace(",", " ") + " руб."


def _unit(measurement: str | None) -> str:
    return _UNITS.get(measurement or "", (measurement or "шт.").lower())


def build_order_note(payload: dict) -> str:
    order_id = payload.get("id")
    items = payload.get("items") or []
    delivery = payload.get("delivery") or {}
    payment = payload.get("paymentMethod") or {}

    lines = [f"ЗАКАЗ №{order_id}", _HR, ""]

    items_total = 0.0
    for it in items:
        price = float(it.get("price") or 0)
        qty = it.get("qty") or 1
        unit = _unit(it.get("measurement"))
        items_total += price * qty

        title = it.get("name") or "Товар"
        if it.get("variantName"):
            title += f" ({it['variantName']})"

        lines.append(_SEP)
        lines.append(title)
        if it.get("sku"):
            lines.append(f"Артикул: {it['sku']}")
        lines.append(f"Количество: {qty} {unit}")
        lines.append(
            f"Стоимость: {_money(price)} x {qty} {unit} = {_money(price * qty)}"
        )
        lines.append("")

    total = float(payload.get("total") or items_total)
    delivery_cost = round(total - items_total, 2)
    order_points = float(payload.get("points") or 0)  # положительный = баллы списаны

    lines.append(f"Стоимость товаров: {_money(items_total)}")
    if delivery_cost > 0:
        lines.append(f"Стоимость доставки: {_money(delivery_cost)}")
    lines += ["", f"ИТОГО: {_money(total)}"]
    if order_points > 0:
        lines.append(f"Оплачено рублями: {_money(payload.get('cash'))}")
        lines.append(f"Оплачено баллами: {int(order_points)}")
    lines += ["", "", "СВОЙСТВА ЗАКАЗА:", _HR]

    if delivery.get("receiverName"):
        lines.append(f"ФИО: {delivery['receiverName']}")
    if delivery.get("receiverPhone"):
        lines.append(f"Телефон: {delivery['receiverPhone']}")
    address = delivery.get("address") or (delivery.get("branch") or {}).get("displayName")
    if address:
        lines.append(f"Адрес доставки: {address}")
    if delivery.get("type"):
        lines.append(
            f"Способ доставки: {_DELIVERY_TYPE.get(delivery['type'], delivery['type'])}"
        )
    if delivery.get("userComment") or payload.get("comment"):
        lines.append(f"Комментарий: {delivery.get('userComment') or payload['comment']}")
    lines.append(f"ССЫЛКА НА ЗАКАЗ В UDS: {_ORDER_LINK.format(order_id=order_id)}")

    lines.append("")
    if payment.get("name"):
        lines.append(f"ОПЛАТА: {payment['name']}")

    return "\n".join(lines)


def build_purchase_note(payload: dict) -> str:
    c = payload.get("customer") or {}
    op_id = payload.get("id")
    points = float(payload.get("points") or 0)
    points_spent = -points if points < 0 else 0  # отрицательный points = списание баллов

    lines = ["ПОКУПКА В UDS"]
    if op_id:
        lines.append(f"Операция №{op_id}")
    lines += [_HR, f"Сумма: {_money(payload.get('total'))}"]
    if points_spent:
        lines.append(f"Оплачено рублями: {_money(payload.get('cash'))}")
        lines.append(f"Оплачено баллами: {int(points_spent)}")
    if payload.get("receiptNumber"):
        lines.append(f"Чек №{payload['receiptNumber']}")
    if c.get("id"):
        lines.append(
            f"ССЫЛКА НА КЛИЕНТА В UDS: {_CUSTOMER_LINK.format(customer_id=c['id'])}"
        )
    return "\n".join(lines)
