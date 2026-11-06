import os
import sys
import torch

print("Python :", sys.executable)
print("PyTorch :", torch.__version__)
print("CUDA disponible :", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU :", torch.cuda.get_device_name(0))
    print("VRAM totale :", round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2), "Go")

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    pipeline
)

from langchain_huggingface import HuggingFacePipeline
from langchain_huggingface import ChatHuggingFace

MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True
)

print("\n[1/4] Chargement du tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
print("OK - Tokenizer charge.")

print("\n[2/4] Chargement de Mistral 7B sur GPU...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="cuda"
)

print("OK - Mistral charge !")
print("Device :", model.device)

print("\n[3/4] Creation du pipeline...")
pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=256,
    do_sample=False,
    pad_token_id=tokenizer.eos_token_id,
    return_full_text=False
)

llm = HuggingFacePipeline(pipeline=pipe)
chat_model = ChatHuggingFace(llm=llm)
print("OK - ChatModel pret.")

print("\n[4/4] Test inference...")
response = chat_model.invoke("Quels sont les symptomes d'une grippe chez un enfant ?")
print("OK - Reponse :")
print(response)
