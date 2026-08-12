#!/usr/bin/env bash
# Objective: a fork pull request must not be able to run attacker-controlled
# code with repository secrets in scope.
#
# This check is deliberately NOT `grep -q pull_request_target ci.yml`. That test
# gives two wrong verdicts: it passes a learner who renamed the trigger while
# still handing DEPLOY_TOKEN to a build of the fork head, and it fails a learner
# who correctly kept the trigger but removed secret scope. Grading is done
# server-side by validate_cicd_lab, which re-derives the exposure from the live
# workflow state (trigger + checkout ref + secret scope together).
cicd-pipeline verify-workflow --no-fork-pr-secret-exposure
