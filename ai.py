#! /bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import openai
import distro
import pickle
import signal
import subprocess
import argparse
import re


def cache(maxsize=128):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Bypass the cache if env var is set
            if os.environ.get("NOCACHE"):
                return func(*args, **kwargs)
            key = str(args) + str(kwargs)

            # create the cache directory if it doesn't exist
            if not os.path.exists(os.path.expanduser("~/.cache/bashai")):
                os.mkdir(os.path.expanduser("~/.cache/bashai"))

            # load the cache
            try:
                with open(os.path.expanduser("~/.cache/bashai/cache.pkl"), "rb") as f:
                    cache = pickle.load(f)
            except (FileNotFoundError, EOFError):
                cache = {}
            
            if key in cache:
                return cache[key]
            else:
                result = func(*args, **kwargs)
                if len(cache) >= maxsize:
                    cache.popitem()
                cache[key] = result
                with open(os.path.expanduser("~/.cache/bashai/cache.pkl"), "wb") as f:
                    pickle.dump(cache, f)
                return result
        return wrapper
    return decorator

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
        # make sure the directory exists
        if not os.path.exists(os.path.expanduser("~/.config")):
            os.mkdir(os.path.expanduser("~/.config"))
        with open(os.path.expanduser("~/.config/openai"), "w") as f:
            f.write(openai.api_key)

@cache()
def get_cmd(prompt, context_files=[]):
    # add info about the system to the prompt. E.g. ubuntu, arch, etc.
    distribution = distro.like()
    context_prompt = ""
    # add the current folder to the prompt
    if len(context_files) > 0:
        context_prompt = "The command is executed in folder %s contining the following list of files:\n" % (os.getcwd())
        # add the files to the prompt
        context_prompt += "\n".join(context_files)
            


    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt="Running on Linux like %s. %s\nSingle bash command to %s\n" % (distribution, context_prompt, prompt),
        temperature=0,
        max_tokens=50,
        top_p=1,
    )
    cmd = response.get("choices")[0].get("text", "echo 'No command found.'")
    # trim the cmd
    cmd = cmd.strip()
    return cmd

@cache()
def get_explaination(cmd):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt="Explain what is the purpose of command with details for each option: %s \n" % cmd,
        temperature=0,
        max_tokens=250,
        top_p=1,
    )
    return response.get("choices")[0].get("text", "No explaination found.")


def highlight(cmd, explanation):
    for x in set(cmd.split(" ")):
        x_strip = x.strip()
        x_replace = "\033[1;33m%s\033[0m" % x_strip

        #escape the special characters
        x_strip = re.escape(x_strip)

        explanation = re.sub("([\s'\"`\.,;:])%s([\s'\"`\.,;:])" % x_strip, "\\1%s\\2" % x_replace, explanation)
    return explanation

# Control-C to exit
def signal_handler(sig, frame):
    print("\nExiting.")
    sys.exit(0)


if __name__ == "__main__":
    # get the command from the user
    if len(sys.argv) < 2:
        print("Please provide a command to execute.")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', action='store_true', help='include folder content as context to the request.')
    parser.add_argument('-e', action='store_true', help='explain the generated command.')
    parser.add_argument('text', nargs='+', help='your query to the ai')

    args = parser.parse_args()
    context = args.c
    context_files = []
    if context:
        context_files = os.listdir(os.getcwd())

    prompt = " ".join(args.text)

    # setup control-c handler
    signal.signal(signal.SIGINT, signal_handler)

    # get the api key
    get_api_key()

    # # get the prompt
    # prompt = " ".join(sys.argv[1:])

    # get the command from the ai
    cmd = get_cmd(prompt, context_files=context_files)


    if args.e:
        explaination = get_explaination(cmd)
        h_explaination = highlight(cmd, explaination.strip())
        print("\n --- \033[1;31m Explaination: \033[0m --- ")
        print(h_explaination)
        print("")


    # print the command colorized
    print("AI wants to execute \n\033[1;32m%s\033[0m\n" % cmd)



    # validate the command
    if not input("Do you want to execute this command? [Y/n] ").lower() == "n":
        # execute the command with Popen and save it to the history

        # retrieve the shell
        shell = os.environ.get("SHELL")
        # if no shell is set, use bash
        if shell is None:
            shell = "/bin/bash"
        # build the command
        # cmd = "%s -c '%s'; history -w" % (shell, cmd)
        subprocess.call(cmd, shell=True)
        # os.system(cmd)
        

