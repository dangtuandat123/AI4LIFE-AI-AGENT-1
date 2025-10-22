import time
from typing import Optional, Sequence, TYPE_CHECKING

from colorama import Fore, Style, init
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_ollama import ChatOllama, OllamaEmbeddings
from ollama._types import ResponseError
from pydantic import BaseModel
from langchain.agents.structured_output import ToolStrategy 
from langchain.agents import create_agent
from config import EMBEDDING_MODEL_NAME, LLM_MODEL_NAME, LLM_TEMPERATURE

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


def create_agent_basic(response_struct: Optional[type[BaseModel]] = None):
    llm = ChatOllama(model=LLM_MODEL_NAME, temperature=LLM_TEMPERATURE)
    return llm.with_structured_output(response_struct)


def create_agent_react(tools, response_struct,system_prompt):
    llm = ChatOllama(model=LLM_MODEL_NAME, temperature=LLM_TEMPERATURE)
    agent =create_agent(
        llm,
        tools=tools,
        system_prompt=system_prompt,
        response_format=response_struct,
        debug=True
        
    )
    return agent


def get_embedding_model():
    embedding_model = OllamaEmbeddings(model=EMBEDDING_MODEL_NAME)
    return embedding_model


def invoke_with_retry(chain, payload, state, agent_label, reminder=None, max_attempts=5):
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = chain.invoke(payload)
            if isinstance(result, AIMessage):
                result.tool_calls = []
                result.additional_kwargs.pop("tool_calls", None)
                result.additional_kwargs.pop("function_call", None)
            return result
        except OutputParserException as exc:
            last_error = exc
            print_colored(
                f"{agent_label} structured output error on attempt {attempt}: {exc}",
                "red",
            )
            if attempt == max_attempts:
                break
            if reminder:
                state["messages"].append(HumanMessage(content=reminder))
            time.sleep(3)
        except ResponseError as exc:
            last_error = exc
            print_colored(
                f"{agent_label} API error on attempt {attempt}: {exc}",
                "red",
            )
            if attempt == max_attempts:
                break
            time.sleep(3)
    if last_error:
        raise last_error
    raise RuntimeError(f"{agent_label} failed without returning a response.")


def print_colored(text: str, color: str = "green") -> None:
    init(autoreset=True)

    color_dict = {
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "blue": Fore.BLUE,
        "magenta": Fore.MAGENTA,
        "cyan": Fore.CYAN,
        "white": Fore.WHITE,
    }

    chosen_color = color_dict.get(color.lower(), Fore.GREEN)
    try:
        print(f"{chosen_color}{text}{Style.RESET_ALL}")
    except UnicodeEncodeError:
        safe_text = text.encode("ascii", "ignore").decode("ascii")
        print(f"{chosen_color}{safe_text}{Style.RESET_ALL}")
