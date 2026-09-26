# from agents.graph import build_graph


# graph = build_graph()


# def chat(user_id: str):

#     print(f"\nStarting conversation for {user_id}")
#     print("Type 'exit' to stop.\n")

#     config = {
#         "configurable": {
#             "thread_id": user_id
#         }
#     }

#     while True:

#         message = input("You: ")

#         if message.lower() in ["exit", "quit"]:
#             break

#         result = graph.invoke(
#             {
#                 "user_query": message
#             },
#             config=config
#         )

#         print("\nCuraTera:", result.get("final_response"))

#         print("\nCurrent Profile:")
#         print(result.get("citizen_profile"))

#         print()


# if __name__ == "__main__":

#     user_id = input("Enter user ID: ")

#     chat(user_id)


from agents.graph import build_graph


graph = build_graph()


def chat(user_id: str):

    print(f"\nStarting conversation for {user_id}")
    print("Type 'exit' to stop.\n")

    config = {
        "configurable": {
            "thread_id": user_id
        }
    }

    while True:

        message = input("You: ")

        if message.lower() in ["exit", "quit"]:
            break

        result = graph.invoke(
            {
                "user_query": message
            },
            config=config
        )

        final_response = result.get(
            "final_response",
            {}
        )

        print("\nCuraTera:")

        if isinstance(final_response, dict):
            print(
                final_response.get(
                    "message",
                    "I couldn't generate a response."
                )
            )

        else:
            print(final_response)

        print("\nCurrent Profile:")
        print(
            result.get(
                "citizen_profile"
            )
        )

        print()


if __name__ == "__main__":

    user_id = input(
        "Enter user ID: "
    )

    chat(user_id)

# .\venv\Scripts\python.exe api.py
# .\venv\Scripts\python.exe ml/opportunity/scheduler
# cd "C:\Users\ss\OneDrive\SISTec hackathon\CuraTeraApp\android"
# .\gradlew assembleDebug
# adb install -r "C:\Users\ss\OneDrive\SISTec hackathon\CuraTeraApp\android\app\build\outputs\apk\debug\app-debug.apk"
# cd "C:\Users\ss\OneDrive\SISTec hackathon\CuraTeraApp"
# npx react-native start
# ipconfig | findstr IPv4
