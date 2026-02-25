from agent import MCPAgent


def main():

    agent = MCPAgent()

    print("\nMCP Agent Ready\n(type 'exit' to quit)\n")

    while True:

        prompt = input("> ")

        if prompt.lower() in ["exit", "quit"]:
            break

        result = agent.run(prompt)

        print("\n", result, "\n")


if __name__ == "__main__":
    main()
