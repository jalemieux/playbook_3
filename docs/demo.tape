Output demo.gif
Set FontSize 14
Set Width 1200
Set Height 600
Set TypingSpeed 50ms
Set Shell "bash"
Set Theme "Catppuccin Mocha"

# Build the image silently first
Hide
Type "docker build -q -t playbook_3 . 2>/dev/null"
Enter
Sleep 15s
Show

# Run the agent
Type "docker run -it --env-file .env playbook_3"
Enter
Sleep 5s

# Greet
Type "Hi there!"
Enter
Sleep 10s

# Ask the question
Type "what is the 45th number in fibonacci's sequence"
Enter
Sleep 30s
