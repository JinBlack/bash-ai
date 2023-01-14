#!/bin/bash

# get the directory of the current script
SCRIPT_DIR=$(cd $(dirname $0); pwd)

# Get the current shell name
CURRENT_SHELL=$(basename "$SHELL")

echo "Current shell: $CURRENT_SHELL"

# add the script directory to the PATH
if [ "$CURRENT_SHELL" = "bash" ]; then
    echo "export PATH=\$PATH:$SCRIPT_DIR" >> ~/.bashrc
    echo "Added $SCRIPT_DIR to PATH in .bashrc"
elif [ "$CURRENT_SHELL" = "zsh" ]; then
    echo "export PATH=\$PATH:$SCRIPT_DIR" >> ~/.zshrc
    echo "Added $SCRIPT_DIR to PATH in .zshrc"
elif [ "$CURRENT_SHELL" = "fish" ]; then
    echo "set -g fish_user_paths $SCRIPT_DIR $fish_user_paths" >> ~/.config/fish/config.fish
    echo "Added $SCRIPT_DIR to PATH in fish config"
else
    echo "Unknown shell"
    exit 1
fi


