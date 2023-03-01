# Bash AI

## Install
    git clone https://github.com/JinBlack/bash-ai
    cd bash-ai
    chmod +x install.sh
    ./install.sh

First time you run ai, it will install dependencies in a virtual environment and it will ask for the key to the api. 

You can get the key from [here](https://beta.openai.com/account/api-keys)


## Usage
`ai <what you want to do>`

![Demo gif](https://i.postimg.cc/VNqZh0tV/demo.gif)

### Context
`ai` is aware of the distro used. It will use the correct package manager to install dependencies.

`-c` option will add the content of the current directory to the context. This will generate a better result. But it will significantly increase the number of tokens used.

`-e` option will generate an explanation of the command. This will significantly increase the number of tokens used.


![Context Demo gif](https://i.postimg.cc/gjfFWs3K/context.gif)

