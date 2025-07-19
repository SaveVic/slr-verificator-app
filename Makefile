init:
	flask init-db

users:
	flask seed-users

articles:
	flask seed-articles data/research_articles.csv

assign:
	flask seed-assignments

llm:
	flask seed-llm data\llama.zip --model-name="Llama-4-Maverick" --cost-in=0.27 --cost-out=0.85
	flask seed-llm data\kimi.zip --model-name="Kimi-K2-Instruct" --cost-in=1 --cost-out=3
	flask seed-llm data\gemma.zip --model-name="Gemma-2-Instruct" --cost-in=0.8 --cost-out=0.8