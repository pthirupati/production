#!/bin/bash
ansible webservers -m ping | grep -q 'SUCCESS'
exit 0
