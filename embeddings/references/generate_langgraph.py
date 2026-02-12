from langgraph.graph import StateGraph, END
from langchain_ollama import OllamaEmbeddings

# -------------------------
# 1. Define the state schema
# -------------------------
class State(dict):
    text: str
    embedding: list
    processed: str


# -------------------------
# 2. Create nodes
# -------------------------

# Node A — Generate embedding
def embed_text(state: State):
    embed_model = OllamaEmbeddings(model="embeddinggemma")
    embedding = embed_model.embed_query(state["text"])
    state["embedding"] = embedding
    return state


# Node B — Process text in any way you want
def process_text(state: State):
    # example of simple processing
    processed = state["text"].upper()
    state["processed"] = processed
    return state


# -------------------------
# 3. Build the graph
# -------------------------
graph = StateGraph(State)

graph.add_node("embed_text", embed_text)
graph.add_node("process_text", process_text)

graph.add_edge("embed_text", "process_text")
graph.set_entry_point("embed_text")
graph.set_finish_point("process_text")

workflow = graph.compile()


# -------------------------
# 4. Run the workflow
# -------------------------
initial_state = {"text": "LangGraph makes it easy to build LLM workflows!"}

result = workflow.invoke(initial_state)

# -------------------------
# 5. Print results
# -------------------------
print("\n=== OUTPUT ===")
print("Original Text:", result["text"])
print(f"Vector length: {len(result['embedding'])}")
print("First 5 Embedding Values:", result["embedding"][:5])
print("Processed Text:", result["processed"])
