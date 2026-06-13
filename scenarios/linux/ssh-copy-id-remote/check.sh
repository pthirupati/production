#!/bin/bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=no labuser@remote-server echo fixitlab-ok 2>/dev/null | grep -q fixitlab-ok
