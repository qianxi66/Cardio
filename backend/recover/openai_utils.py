import json
from pathlib import Path
from datetime import datetime
from openai import OpenAI, AzureOpenAI

from .config import (
    openai_key,
    use_azure_openai,
    azure_openai_endpoint,
    azure_openai_api_key,
    azure_openai_deployment,
    azure_openai_api_version,
)
from .symptoms import symptom_descriptions

if use_azure_openai:
    client = AzureOpenAI(
        api_version=azure_openai_api_version,
        azure_endpoint=azure_openai_endpoint.rstrip("/"),
        api_key=azure_openai_api_key,
    )
    _model = azure_openai_deployment
else:
    client = OpenAI(api_key=openai_key)
    _model = "gpt-4o"

prompt_path = Path(__file__).with_name("prompt.txt")
conversation_system_prompt = open(prompt_path, "r").read(10000000)
key_questions_prompt_path = Path(__file__).with_name("key_questions_prompt.txt")
key_questions_prompt = open(key_questions_prompt_path, "r").read(10000000)
summary_prompt_path = Path(__file__).with_name("summary_prompt.txt")
summary_prompt = open(summary_prompt_path, "r").read(10000000)


def gpt_inference(client, messages, stop=None, model=None, **argv):
    model = model or _model
    kwargs = dict(messages=messages, model=model, stop=stop, **argv)
    if use_azure_openai:
        kwargs.pop("max_tokens", None)
        kwargs["extra_body"] = {"max_completion_tokens": 512}
    else:
        kwargs.setdefault("max_tokens", 512)
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def conversation(messages, wearable_data=None, recent_reports_summaries=None):
    system_messages = [{"role": "system", "content": conversation_system_prompt}]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if wearable_data:
        system_messages.append({
            "role": "system",
            "content": f"Today's wearable data: {json.dumps(wearable_data)}"
        })
    
    system_messages.append({
        "role": "system",
        "content": f"current time: {current_time}"
    })
    
    if recent_reports_summaries:
        system_messages.append({
            "role":"system",
            "content": f"Recent's report: {json.dumps(recent_reports_summaries)}"
        })
        
    return gpt_inference(
        client,
        [*system_messages, *messages],
    )


def key_questions(messages):
    return gpt_inference(
        client,
        [
            {"role": "system", "content": key_questions_prompt},
            {"role": "user", "content": messages},
        ],
        model=_model,
        response_format={"type": "json_object"},
    )


def summary(messages, key_questions, wearable_data=None):
    user_messages = [
        {
            "role": "user",
            "content": "List of all symptoms descriptions"
            + json.dumps(symptom_descriptions),
        },
        {"role": "user", "content": "messages: " + messages},
        {"role": "user", "content": "symptoms: " + key_questions},
    ]
    if wearable_data:
        user_messages.append({
            "role": "user",
            "content": "Wearable sensor data for today: " + json.dumps(wearable_data),
        })
    return gpt_inference(
        client,
        [
            {"role": "system", "content": summary_prompt},
            *user_messages,
        ],
        model=_model,
        response_format={"type": "json_object"},
    )
