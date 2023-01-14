#! /bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import openai

def get_api_key():
    # load the api key from .config/openai
    if os.path.exists(os.path.expanduser("~/.config/openai")):
        with open(os.path.expanduser("~/.config/openai")) as f:
            openai.api_key = f.read().strip()
    else:
        print("No api key found. Please create a file ~/.config/openai with your api key in it.")
        # ask for key and store it
        openai.api_key = input("Please enter your api key: ")
        if openai.api_key == "":
            print("No api key provided. Exiting.")
            sys.exit(1)
        with open(os.path.expanduser("~/.config/openai"), "w") as f:
            f.write(openai.api_key)


if __name__ == "__main__":
    get_api_key()
    # get the command from the user
    if len(sys.argv) < 2:
        print("Please provide a command to execute.")
        sys.exit(1)
    prompt = " ".join(sys.argv[1:])
   
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt="signle bash command to %s" % prompt,
        temperature=0,
        max_tokens=50,
        top_p=1,
    )
    cmd = response.get("choices")[0].get("text", "echo 'No command found.'")
    # trim the cmd
    cmd = cmd.strip()
    # print the command colorized
    print("AI want to execute \n\033[1;32m%s\033[0m\n" % cmd)
    # validate the command
    if not input("Do you want to execute this command? [Y/n] ").lower() == "n":
        os.system(cmd)
