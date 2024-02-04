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
from collections import OrderedDict
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
# logging goes into stderr
logging.basicConfig(level=logging.DEBUG, format="[%(name)s]\t%(asctime)s - %(levelname)s \t %(message)s")


VERSION = "0.3.0"
CACHE_FOLDER = "~/.cache/bashai"

def cache(maxsize=128):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Bypass the cache if env var is set
            if os.environ.get("NOCACHE"):
                return func(*args, **kwargs)
            key = str(args) + str(kwargs)

            # create the cache directory if it doesn't exist
            if not os.path.exists(os.path.expanduser(CACHE_FOLDER)):
                os.mkdir(os.path.expanduser(CACHE_FOLDER))

            # load the cache
            try:
                cache_folder = os.path.expanduser(CACHE_FOLDER)
                with open(os.path.join(cache_folder, "cache.pkl"), "rb") as f:
                    cache = pickle.load(f)
            except (FileNotFoundError, EOFError):
                cache = OrderedDict()

            if not isinstance(cache, OrderedDict):
                cache = OrderedDict()

            if key in cache:
                return cache[key]
            else:
                result = func(*args, **kwargs)
                if len(cache) >= maxsize:
                    # remove the oldest entry
                    cache.popitem(last=False)

                cache[key] = result
                cache_folder = os.path.expanduser(CACHE_FOLDER)
                with open(os.path.join(cache_folder, "cache.pkl"), "wb") as f:
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

def get_context_files():
    context_files = os.listdir(os.getcwd())
    context_prompt = ""
    # add the current folder to the prompt
    if len(context_files) > 0:
        context_prompt = "The command is executed in folder %s contining the following list of files:\n" % (os.getcwd())
        # add the files to the prompt
        context_prompt += "\n".join(context_files)
    return context_prompt

def get_context_process_list():
    context_prompt = ""
    # list all processes
    process_list = subprocess.check_output(["ps", "-A", "-o", "pid,ppid,cmd"]).decode("utf-8")
    context_prompt += "The following processes are running: %s\n" % process_list
    return context_prompt

def get_context_env():
    context_prompt = ""
    # list all environment variables
    env = os.environ
    context_prompt += "The following environment variables are set: %s\n" % env
    return context_prompt

def get_context_users():
    context_prompt = ""
    # list all users
    users = subprocess.check_output(["getent", "passwd"]).decode("utf-8")
    context_prompt += "The following users are defined: %s\n" % users
    return context_prompt

def get_context_groups():
    context_prompt = ""
    # list all groups
    groups = subprocess.check_output(["getent", "group"]).decode("utf-8")
    context_prompt += "The following groups are defined: %s\n" % groups
    return context_prompt

def get_context_network_interfaces():
    context_prompt = ""
    # list all network interfaces
    interfaces = subprocess.check_output(["ip", "link"]).decode("utf-8")
    context_prompt += "The following network interfaces are defined: %s\n" % interfaces
    return context_prompt

def get_context_network_routes():
    context_prompt = ""
    # list all network interfaces
    routes = subprocess.check_output(["ip", "route"]).decode("utf-8")
    context_prompt += "The following network routes are defined: %s\n" % routes
    return context_prompt

def get_context_iptables():
    context_prompt = ""
    # list all iptables rules
    iptables = subprocess.check_output(["sudo", "iptables", "-L"]).decode("utf-8")
    context_prompt += "The following iptables rules are defined: %s\n" % iptables
    return context_prompt


CONTEXT = [
    {"name": "List of files in the current directory", "function": get_context_files},
    {"name": "List of processes", "function": get_context_process_list},
    # {"name": "List of environment variables", "function": get_context_env}, # This looks like a security issue
    {"name": "List of users", "function": get_context_users},
    {"name": "List of groups", "function": get_context_groups},
    {"name": "List of network interfaces", "function": get_context_network_interfaces},
    {"name": "List of network routes", "function": get_context_network_routes},
    {"name": "List of iptables rules", "function": get_context_iptables},
]


def load_history():
    # create the cache directory if it doesn't exist
    if not os.path.exists(os.path.expanduser(CACHE_FOLDER)):
        os.mkdir(os.path.expanduser(CACHE_FOLDER))

    # load the history from .chat_history
    cache_folder = os.path.expanduser(CACHE_FOLDER)
    path = os.path.join(cache_folder, "chat_history")
    if os.path.exists(path):
        with open(path, "rb") as f:
            history = pickle.load(f)
    else:
        history = []
    return history


def save_history(history, limit=50):
    # create the cache directory if it doesn't exist
    if not os.path.exists(os.path.expanduser(CACHE_FOLDER)):
        os.mkdir(os.path.expanduser(CACHE_FOLDER))

    # save the history to chat_history
    cache_folder = os.path.expanduser(CACHE_FOLDER)
    with open(os.path.join(cache_folder, "chat_history"), "wb") as f:
        history = history[-limit:]
        pickle.dump(history, f)

def clean_history():
    # create the cache directory if it doesn't exist
    if not os.path.exists(os.path.expanduser(CACHE_FOLDER)):
        os.mkdir(os.path.expanduser(CACHE_FOLDER))

    cache_folder = os.path.expanduser(CACHE_FOLDER)
    path = os.path.join(cache_folder, "chat_history")
    if os.path.exists(path):
        os.unlink(path)
    

def chat(prompt):
    history = load_history()
    # esitmate the length of the history in words
    while sum([len(h["content"].split()) for h in history]) > 2000:
        # skip the first message that should be the system message
        history = history[1:]

    print("History length: %s" % sum([len(h["content"].split()) for h in history]))

    if len(history) == 0 or len([h for h in history if h["role"] == "system"]) == 0:
        distribution = distro.name()
        history.append({"role": "system", "content": "You are a helpful assistant. Answer as concisely as possible. This machine is running Linux %s." % distribution})

    history.append({"role": "user", "content": prompt})
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=history)
    content = response.get("choices")[0].message.content
    # trim the content
    content = content.strip()
    history.append({"role": "assistant", "content": content})
    save_history(history)
    return content

@cache()
def get_cmd(prompt, context_prompt=""):
    # add info about the system to the prompt. E.g. ubuntu, arch, etc.
    distribution = distro.like()
    if distribution is None or distribution == "":
        distribution = distro.name()
    log.debug("Distribution: %s" % distribution)

    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt="Running on Linux like %s. %s\nSingle bash command to %s\n" % (distribution, context_prompt, prompt),
        temperature=0,
        max_tokens=100,
        top_p=1,
    )
    cmd = response.get("choices")[0].get("text", "echo 'No command found.'")
    # trim the cmd
    cmd = cmd.strip()
    return cmd


@cache()
def get_cmd_list(prompt, context_files=[], n=5):
    # add info about the system to the prompt. E.g. ubuntu, arch, etc.
    distribution = distro.like()
    if distribution is None or distribution == "":
        distribution = distro.name()
    log.debug("Distribution: %s" % distribution)
    context_prompt = get_context_files(context_files)    

    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt="Running on Linux like %s. %s\n Generate a single bash command to %s\n" % (distribution, context_prompt, prompt),
        temperature=0.9,
        max_tokens=50,
        top_p=1,
        n=n,
    )
    cmd_list = [x.get("text", "echo 'No command found.'") for x in response.get("choices")]
    # trim the cmd
    cmd_list = list(set([x.strip() for x in cmd_list]))
    return cmd_list


@cache()
def get_needed_context(cmd):
    context_list = ""
    for i in range(len(CONTEXT)):
        context_list += "%s ) %s\n" % (i, CONTEXT[i]["name"])

    prompt = "If you need to generate a signle bash command to %s, which of this context you need:\n%s\n Your output is a number.\n If none of the above context is usefull the output is -1.\n" % (cmd, context_list)

    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt=prompt,
        temperature=0,
        max_tokens=4,
        top_p=1,
    )
    choice = response.get("choices")[0].get("text", "No explanation found.").strip()
    try:
        choice = int(choice.strip())
    except:
        #print the wrong chice in red
        print("Wrong context: \033[1;31m%s\033[0m" % choice)
        choice = -1

    return choice


@cache()
def get_explaination(cmd):
    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt="Explain what is the purpose of command with details for each option: %s \n" % cmd,
        temperature=0,
        max_tokens=250,
        top_p=1,
    )
    explanation = response.get("choices")[0].get("text", "No explanation found.")
    explanation = explanation.replace("\n\n", "\n")
    return explanation


def highlight(cmd, explanation):
    for x in set(cmd.split(" ")):
        x_strip = x.strip()
        x_replace = "\033[1;33m%s\033[0m" % x_strip

        #escape the special characters
        x_strip = re.escape(x_strip)

        explanation = re.sub("([\s'\"`\.,;:])%s([\s'\"`\.,;:])" % x_strip, "\\1%s\\2" % x_replace, explanation)
    return explanation


def square_text(text):
    #retrieve the terminal size using library
    columns, lines = os.get_terminal_size(0)

    # set mono spaced font
    out = "\033[10m"        

    out = "-" * int(columns)
    for line in text.split("\n"):
        for i in range(0, len(line), int(columns)-4):
            out += "\n| %s |" % line[i:i+int(columns)-4].ljust(int(columns)-4)
    out += "\n" + "-" * int(columns)
    return out

    
def print_explaination(cmd):    
    explaination = get_explaination(cmd)
    h_explaination = highlight(cmd, square_text(explaination.strip()))
    print("-" * 27)
    print("| *** \033[1;31m Explaination: \033[0m *** |")
    print(h_explaination)
    print("")


def generate_context_help():
    c_string = ""
    for i in range(len(CONTEXT)):
        c_string += "\t%s) %s\n" % (i, CONTEXT[i]["name"])
    return c_string


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
    parser.add_argument('-c', action='store_true', help='auto select context to be included.')
    parser.add_argument('-C', action='store', type=int, default=-1, choices=range(0, len(CONTEXT)), help='specify which context to include: %s' % generate_context_help())
    parser.add_argument('-e', action='store_true', help='explain the generated command.')
    parser.add_argument('-n', action='store', type=int, default=5, help='number of commands to generate.')
    parser.add_argument('--chat', action='store_true', help='Chat mode.')
    parser.add_argument('--new', action='store_true', help='Clean the chat history.')
    parser.add_argument('text', nargs='+', help='your query to the ai')

    args = parser.parse_args()

    # get the prompt
    prompt = " ".join(args.text)


    # setup control-c handler
    signal.signal(signal.SIGINT, signal_handler)

    # get the api key
    get_api_key()


    context = args.c or args.C >= 0
    context_files = []
    context_prompt = ""
    if context:
        needed_contxt = args.C
        if needed_contxt < 0:
            needed_contxt = get_needed_context(prompt)
        if needed_contxt >= 0:
            print("AI choose to %s as context." % CONTEXT[needed_contxt]["name"])
            context_prompt += CONTEXT[needed_contxt]["function"]()
        if len(context_prompt) > 3000:
            context_prompt = context_prompt[:3000]

    if args.chat:
        if args.new:
            print("Cleaning the chat history.")
            clean_history()
        while True:
            cmd = chat(prompt)
            print("AI: %s" % cmd)
            prompt = input("You: ")
        sys.exit(0)


    # get the command from the ai
    cmd = get_cmd(prompt, context_prompt=context_prompt)


    if args.e:
        print_explaination(cmd)

    # print the command colorized
    print("AI wants to execute \n\033[1;32m%s\033[0m\n" % cmd)


    # validate the command
    if input("Do you want to execute this command? [Y/n] ").lower() == "n":
        # execute the command with Popen and save it to the history
        cmds = get_cmd_list(prompt, context_files=context_files, n=args.n)
        print("Here are some other commands you might want to execute:")
        index = 0
        for cmd in cmds:
            print("%d. \033[1;32m%s\033[0m" % (index, cmd))
            if args.e:
                print_explaination(cmd)
                print("\n")

            index += 1

        choice = input("Do you want to execute one of these commands? [0-%d] " % (index-1))
        if choice.isdigit() and int(choice) < index:
            cmd = cmds[int(choice)]
        else:
            print("No command executed.")
            sys.exit(1)

    # retrieve the shell
    shell = os.environ.get("SHELL")
    # if no shell is set, use bash
    if shell is None:
        shell = "/bin/bash"

    if not os.environ.get("NOHISTORY"):
        # retrieve the history file of the shell depending on the shell
        if shell == "/bin/bash":
            history_file = os.path.expanduser("~/.bash_history")
        elif shell == "/bin/zsh":
            history_file = os.path.expanduser("~/.zhistory")
            # subprocess.call("fc -R", shell=True, executable=shell)
        elif shell == "/bin/fish":
            history_file = os.path.expanduser("~/.local/share/fish/fish_history")
        else:
            history_file = None
            #log.warning("Shell %s not supported. History will not be saved." % shell)
        
        # save the command to the history
        if history_file is not None:
            with open(history_file, "a") as f:
                f.write(cmd + "\n")        
            print("History saved.")

    # Execute the command in the current shell (bash, zsh, fish, etc.)
    subprocess.call(cmd, shell=True, executable=shell)





