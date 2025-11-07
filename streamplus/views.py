import json
import re
import traceback
from datetime import datetime
from uuid import uuid4

from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

import google.generativeai as genai

# Configure Google Generative AI
genai.configure(api_key=settings.GOOGLE_API_KEY)
# Resolve available models dynamically and cache result
_RESOLVED_MODELS = None


PRODUCT_CATALOG = [
	{
		"id": "canva-pro",
		"name": "Canva Pro",
		"aliases": ["canva", "canva pro"],
		"price": 249,
		"billing": "per seat / month",
		"perks": "Includes full template library, brand kits, and team collaboration.",
	},
	{
		"id": "netflix-premium",
		"name": "Netflix Premium",
		"aliases": ["netflix", "netflix premium"],
		"price": 499,
		"billing": "per account / month",
		"perks": "Supports up to 4K UHD streaming with multiple profiles.",
	},
	{
		"id": "spotify-premium",
		"name": "Spotify Premium",
		"aliases": ["spotify", "spotify premium"],
		"price": 189,
		"billing": "per account / month",
		"perks": "Ad-free listening, offline downloads, and high fidelity audio.",
	},
	{
		"id": "disney-plus",
		"name": "Disney+",
		"aliases": ["disney", "disney+", "disney plus"],
		"price": 299,
		"billing": "per account / month",
		"perks": "Access to Disney, Pixar, Marvel, Star Wars, and National Geographic.",
	},
	{
		"id": "amazon-prime",
		"name": "Amazon Prime Video",
		"aliases": ["amazon", "prime", "prime video", "amazon prime"],
		"price": 179,
		"billing": "per account / month",
		"perks": "Movies, series, and originals with multi-device streaming.",
	},
]

ORDER_KEYWORDS = {"order", "buy", "purchase", "subscribe", "get", "reserve"}

def _resolve_models():
	global _RESOLVED_MODELS
	if _RESOLVED_MODELS is not None:
		return _RESOLVED_MODELS
	try:
		models = list(genai.list_models())
		# Prefer flash-8b/flash/pro families that support generateContent
		names = []
		for m in models:
			methods = getattr(m, "supported_generation_methods", []) or []
			if "generateContent" in methods:
				names.append(getattr(m, "name", "").replace("models/", ""))
		# Fallback order hints if list is empty
		if not names:
			names = [
				"gemini-1.5-flash-8b-latest",
				"gemini-1.5-flash-8b",
				"gemini-1.5-flash-latest",
				"gemini-1.5-flash-001",
				"gemini-1.5-pro-latest",
				"gemini-1.0-pro",
			]
		_RESOLVED_MODELS = names
		print("[StreamBot] Available models:", names)
		return _RESOLVED_MODELS
	except Exception as e:
		print("[StreamBot] list_models failed:", str(e))
		_RESOLVED_MODELS = [
			"gemini-1.5-flash-8b-latest",
			"gemini-1.5-flash-8b",
			"gemini-1.5-flash-001",
			"gemini-1.0-pro",
		]
	return _RESOLVED_MODELS


def _find_product(message: str):
	text = message.lower()
	for product in PRODUCT_CATALOG:
		for alias in product["aliases"]:
			if alias in text:
				return product
	return None


def _extract_quantity(message: str) -> int:
	match = re.search(r"\b(\d{1,2})\b", message)
	if match:
		qty = int(match.group(1))
		return max(1, min(qty, 10))
	return 1


def _format_currency(value: float) -> str:
	return f"₱{value:,.0f}"


def _create_order_id() -> str:
	return f"ORD-{datetime.now().strftime('%Y%m%d')}-{str(uuid4())[:8].upper()}"


def _parse_contact_details(message: str):
	email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", message)
	email = email_match.group(0) if email_match else None
	name = None
	if email:
		name_candidate = message.replace(email, " ")
		name_candidate = re.sub(r"[-:,]", " ", name_candidate)
		name_candidate = re.sub(r"\s+", " ", name_candidate).strip()
		if name_candidate:
			name = name_candidate.title()
	return name, email


def _format_receipt(order: dict) -> str:
	lines = [
		"🧾 Streamplus Virtual Receipt",
		f"Receipt ID: {order['order_id']}",
		f"Date: {order['created_at'].strftime('%d %b %Y %I:%M %p')}",
		f"Customer: {order['customer_name']}",
		f"Email: {order['customer_email']}",
		"",
		"Order Summary:",
		f"- {order['quantity']} × {order['product_name']} ({order['billing']}) — {_format_currency(order['item_price'])}",
		f"Subtotal: {_format_currency(order['subtotal'])}",
		f"Platform Fee: {_format_currency(order['platform_fee'])}",
		f"Total Due: {_format_currency(order['total'])}",
		"",
		"Payment Options:",
		"- GCash: 0906-508-8846 (Streamplus Premium Hub)",
		"- BPI: 1234-5678-90 (Streamplus Trading)",
		"",
		"We'll activate your access within 5-10 minutes after payment confirmation. Send your proof of payment via Messenger or email to streamplushub@gmail.com.",
	]
	return "\n".join(lines)


def _summarize_orders(orders: list[dict]) -> str:
	recent = orders[-3:]
	lines = ["Here are your recent Streamplus orders:"]
	for order in recent[::-1]:
		lines.append(
			f"- {order['order_id']} • {order['product_name']} × {order['quantity']} • {_format_currency(order['total'])} • {order['created_at'].strftime('%d %b %Y %I:%M %p')}"
		)
	lines.append("Reply with a product name if you'd like to start a new order.")
	return "\n".join(lines)


def _handle_order_flow(message: str, session) -> str | None:
	text = message.lower()
	orders = session.get("streambot_orders", [])
	active_order = session.get("streambot_order_state", {})

	if "receipt" in text:
		if orders:
			receipt = _format_receipt(orders[-1])
			return f"Here's your latest receipt:\n\n{receipt}"
		return (
			"I don't see a completed order yet. Tell me which product you'd like to buy and I'll prepare a receipt for you."
		)

	if "orders" in text or "history" in text or "summary" in text:
		if orders:
			return _summarize_orders(orders)
		return "No orders on file yet. Ask for a product and say \"order\" to get started."

	if active_order and any(
		word in text for word in {"cancel", "nevermind", "never mind", "stop"}
	):
		session["streambot_order_state"] = {}
		session.modified = True
		return "No problem -- I cleared the pending order. Let me know if you'd like to try again."

	if active_order and active_order.get("status") == "awaiting_details":
		name, email = _parse_contact_details(message)
		if not email:
			return (
				"Almost done! Please share the name and email for the receipt in one message. "
				"Example: Juan Dela Cruz - juandelacruz@email.com"
			)
		customer_name = name or "Valued Customer"
		quantity = active_order["quantity"]
		product = active_order["product"]
		item_price = product["price"]
		subtotal = item_price * quantity
		platform_fee = 20
		total = subtotal + platform_fee
		order_payload = {
			"order_id": _create_order_id(),
			"product_id": product["id"],
			"product_name": product["name"],
			"billing": product["billing"],
			"quantity": quantity,
			"item_price": item_price,
			"subtotal": subtotal,
			"platform_fee": platform_fee,
			"total": total,
			"customer_name": customer_name,
			"customer_email": email,
			"created_at": datetime.now(),
		}
		orders.append(order_payload)
		session["streambot_orders"] = orders
		session["streambot_order_state"] = {}
		session["streambot_last_intent"] = "order"
		session["streambot_last_product"] = product["name"]
		session.modified = True
		receipt = _format_receipt(order_payload)
		return (
			f"Thanks, {customer_name}! Your {product['name']} order is confirmed. "
			f"I've sent the virtual receipt below."
			f"\n\n{receipt}"
		)

	product = _find_product(message)
	if product:
		session["streambot_last_product"] = product["name"]
		session["streambot_last_intent"] = "product-info"
		session.modified = True
		if any(keyword in text for keyword in ORDER_KEYWORDS):
			quantity = _extract_quantity(message)
			total = product["price"] * quantity
			session["streambot_order_state"] = {
				"status": "awaiting_details",
				"product": product,
				"quantity": quantity,
			}
			session["streambot_last_intent"] = "order"
			session.modified = True
			return (
				f"Awesome choice! I reserved {quantity} × {product['name']} ({product['billing']}). "
				f"That's {_format_currency(product['price'])} each, total {_format_currency(total)}. "
				"Please share the account name and email for the receipt (example: Juan Dela Cruz - juan@email.com)."
			)
		return (
			f"{product['name']} costs {_format_currency(product['price'])} {product['billing']}. "
			f"{product['perks']} Reply with \"order\" plus the product name if you'd like me to reserve it for you."
		)

	return None


def home_view(request: HttpRequest) -> HttpResponse:
	return render(request, "home.html")

def about_view(request: HttpRequest) -> HttpResponse:
	return render(request, "about.html")

def products_view(request: HttpRequest) -> HttpResponse:
	return render(request, "products.html")

def marketing_view(request: HttpRequest) -> HttpResponse:
	return render(request, "marketing.html")

def contact_view(request: HttpRequest) -> HttpResponse:
	return render(request, "contact.html")

@csrf_exempt
def chatbot_view(request: HttpRequest) -> JsonResponse:
	if request.method != "POST":
		return JsonResponse({"error": "Only POST allowed"}, status=405)

	try:
		data = json.loads(request.body.decode("utf-8"))
		user_message = (data.get("message") or "").strip()
	except Exception:
		return JsonResponse({"error": "Invalid JSON"}, status=400)

	if not user_message:
		return JsonResponse({"reply": "Please type a message so I can help."})

	session = request.session

	manual_reply = _handle_order_flow(user_message, session)
	if manual_reply:
		return JsonResponse({"reply": manual_reply})

	system_preamble = (
		"You are StreamBot, the helpful conversational sales assistant for Streamplus Premium Hub. "
		"Streamplus sells affordable shared premium subscriptions: Canva Pro, Netflix Premium, Spotify Premium, Disney+, and Amazon Prime. "
		"Focus on e-commerce style replies: confirm product benefits, pricing, upsell bundles, outline payment options (GCash 0906-508-8846, BPI 1234-5678-90), and explain activation timelines. "
		"When users ask about orders or upgrades, keep answers concise (2–4 sentences or up to 4 short bullet points) and drive toward closing the sale. "
		"If exact pricing is unavailable, give a range and invite them to message support. "
		"Contact info: 0906-508-8846, streamplushub@gmail.com, www.streampluspremiun.com, Casillejos, Zambales."
	)

	# Optional: brief session memory (used only to inform AI context)
	last_intent = session.get("streambot_last_intent")
	last_product = session.get("streambot_last_product")

	try:
		last_err = None
		# Include brief context and last turn memory
		history_hint = ""
		if last_intent:
			history_hint = f"Previously discussed intent: {last_intent}. "
		if last_product:
			history_hint += f"Previously discussed product: {last_product}. "
		parts = [
			system_preamble,
			"Context: " + history_hint,
			"User: " + user_message,
			"Assistant:" ,
		]

		gen_cfg = {
			"temperature": 0.6,
			"top_p": 0.8,
			"top_k": 40,
			"max_output_tokens": 256,
		}
		for candidate in _resolve_models():
			try:
				model = genai.GenerativeModel(candidate, generation_config=gen_cfg)
				print(f"[StreamBot] Using model: {candidate}")
				response = model.generate_content(parts)
				ai_text = (getattr(response, "text", None) or "").strip()
				if not ai_text:
					block_reason = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
					if block_reason:
						return JsonResponse({"reply": f"AI blocked the request ({block_reason}). Try rephrasing."}, status=200)
					# If empty, try next model
					continue
				return JsonResponse({"reply": ai_text})
			except Exception as me:
				last_err = me
				continue

		# If all candidates failed
		raise last_err or RuntimeError("No available Gemini model produced a response")
	except Exception as e:
		print("[StreamBot] Error:", getattr(e, 'message', str(e)))
		traceback.print_exc()
		return JsonResponse({"reply": f"AI error: {str(e)}"}, status=200)


