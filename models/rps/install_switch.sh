#!/usr/bin/env bash

# this script will install the switch and switch-hawaii-core repositories
# in subdirectories under this one

# this restores the version used for Matthias Fripp's presentation to the EUCI conference
# on 2016-01-28.

git clone https://github.com/switch-model/switch.git
cd switch
git checkout 322f065345b4b7bb6d9d36914f3b47776a10fa1c
cd ..

git clone https://github.com/switch-model/switch-hawaii-core.git
cd switch-hawaii-core
git checkout b9b14ea20f148dca0347ac4761f841bf0e31f84e
cd ..

echo "switch and switch-hawaii-core repositories have been installed"
