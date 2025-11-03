import json
import traceback
from django.conf import settings
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

import google.generativeai as genai

# Configure Google Generative AI
genai.configure(api_key=settings.GOOGLE_API_KEY)
# Resolve available models dynamically and cache result
_RESOLVED_MODELS = None

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

	system_preamble = (
		"You are StreamBot, the helpful assistant for Streamplus Premium Hub. "
		"Streamplus sells affordable shared premium subscriptions: Canva Pro, Netflix Premium, Spotify Premium, Disney+, and Amazon Prime. "
		"Be concise, friendly, and specific to the business. Offer bundles, referral perks, promos, and how to contact support. "
		"Style: short but detailed and precise. Limit answers to 2–4 sentences or up to 4 short bullet points. No fluff. "
		"If pricing is unknown, describe typical ranges and invite the user to contact support. "
		"Contact info: 0906-508-8846, streamplushub@gmail.com, www.streampluspremiun.com, Casillejos, Zambales."
	)
	
	# Optional: brief session memory (used only to inform AI context)
	session = request.session
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


