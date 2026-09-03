from hebom import Room
room = Room()
room.pass_({"rows": 120, "columns": ["name", "phone"]}, recipient="summarizer")
print(room.take(recipient="summarizer"))
