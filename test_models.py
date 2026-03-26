import google.generativeai as genai

genai.configure(api_key='AIzaSyAzbBrd5TbsNvTzn8J789qYwPjHehZs2rQ')
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"Supported model: {m.name}")
except Exception as e:
    print("Error:", e)
