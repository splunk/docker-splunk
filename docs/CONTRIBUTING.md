# Contributing to the Project

This document is the single source of truth on contributing towards this codebase. Please feel free to browse the open issues and file new ones - all feedback is welcome!

## Topics

* [Prerequisites](#prerequisites)
    * [Contributor License Agreement](#contributor-license-agreement)
    * [Code of Conduct](#code-of-conduct)
    * [Setup development environment](#setup-development-environment)
* [Contribution Workflow](#contribution-workflow)
    * [Feature Requests and Bug Reports](#feature-requests-and-bug-reports)
    * [Fixing Issues](#fixing-issues)
    * [Pull Requests](#pull-requests)
    * [Code Review](#code-review)
    * [Testing](#testing)
    * [Documentation](#documentation)
* [Maintainers](#maintainers)

## Prerequisites
When contributing to this repository, please first discuss the change you wish to make via a GitHub issue, Slack message, email, or via other channels with the owners of this repository.

##### Contributor License Agreement
At the moment, we can only accept pull requests submitted from either:
* Splunk employees or
* Individuals that have signed our contribution agreement

If you wish to be a contributing member of our community, please see the agreement [for individuals](https://www.splunk.com/goto/individualcontributions) or [for organizations](https://www.splunk.com/goto/contributions).

##### Code of Conduct
Please make sure to read and observe our [Code of Conduct](contributing/code-of-conduct.md). Please follow it in all of your interactions involving the project.

##### Setup Development Environment
TODO

## Contribution Workflow
Help is always welcome! For example, documentation can always use improvement. There's always code that can be clarified, functionality that can be extended, and tests to be added to guarantee behavior. If you see something you think should be fixed, don't be afraid to own it.

##### Feature Requests and Bug Reports
Have ideas on improvements? See something that needs work? While the community encourages everyone to contribute code, it is also appreciated when someone reports an issue. Please report any issues or bugs you find through [GitHub's issue tracker](https://github.com/splunk/docker-splunk/issues). 

If you are reporting a bug, please include:
* Your operating system name and version
* Any details about your local setup that might be helpful in troubleshooting (ex. Python interpreter version, Ansible version, etc.)
* Detailed steps to reproduce the bug

We'd also like to hear about your propositions and suggestions. Feel free to submit them as issues and:
* Explain in detail how they should work
* Keep the scope as narrow as possible - this will make it easier to implement

##### Fixing Issues
Look through our [issue tracker](https://github.com/splunk/docker-splunk/issues) to find problems to fix! Feel free to comment and tag corresponding stakeholders or full-time maintainers of this project with any questions or concerns.

##### Pull Requests
What is a "pull request"? It informs the project's core developers about the changes you want to review and merge. Once you submit a pull request, it enters a stage of code review where you and others can discuss its potential modifications and even add more commits to it later on. 

If you want to learn more, please consult this [tutorial on how pull requests work](https://help.github.com/articles/using-pull-requests/) in the [GitHub Help Center](https://help.github.com/).

Here's an overview of how you can make a pull request against this project:
1. Fork the [docker-splunk GitHub repository](https://github.com/splunk/docker-splunk/issues)
2. Clone your fork using git and create a branch off develop
    ```
    $ git clone git@github.com:YOUR_GITHUB_USERNAME/docker-splunk.git
    $ cd docker-splunk

    # This project uses 'develop' for all development activity, so create your branch off that
    $ git checkout -b your-bugfix-branch-name develop
    ```
3. Run all the tests to verify your environment
    ```
    $ cd docker-splunk
    $ make test
    ```
4. Make your changes, commit and push once your tests have passed
    ```
    $ git commit -m "<insert helpful commit message>"
    $ git push 
    ```
5. Submit a pull request through the GitHub website using the changes from your forked codebase

##### Code Review
There are two aspects of code review: giving and receiving.

To make it easier for your PR to receive reviews, consider the reviewers will need you to:
* Follow the project coding conventions
* Write good commit messages
* Break large changes into a logical series of smaller patches which individually make easily understandable changes, and in aggregate solve a broader issue

Reviewers, the people giving the review, are highly encouraged to revisit the [Code of Conduct](contributing/code-of-conduct.md) and must go above and beyond to promote a collaborative, respectful community.

When reviewing PRs from others [The Gentle Art of Patch Review](http://sage.thesharps.us/2014/09/01/the-gentle-art-of-patch-review/) suggests an iterative series of focuses which is designed to lead new contributors to positive collaboration without inundating them initially with nuances:
* Is the idea behind the contribution sound?
* Is the contribution architected correctly?
* Is the contribution polished?

For this project, we require that at least 2 approvals are given and a build from our continuous integration system is successful off of your branch. Please note that any new changes made with your existing pull request during review will automatically unapprove and retrigger another build/round of tests.

##### Testing
Testing is the responsibility of all contributors. In general, we try to adhere to [Google's test sizing philosophy](https://testing.googleblog.com/2010/12/test-sizes.html) when structuring tests. 

There are multiple types of tests. The location of the test code varies with type, as do the specifics of the environment needed to successfully run the test.

1. **Small:** Very fine-grained; exercises low-level logic at the scope of a function or a class; no external resources (except possibly a small data file or two, but preferably no file system dependencies whatsoever); very fast execution on the order of seconds
    ```
    $ make small-tests
    ```

2. **Medium:** Exercises interaction between discrete components; may have file system dependencies or run multiple processes; runs on the order of minutes
    ```
    $ make medium-tests
    ```

3. **Large:** Exercises the entire system, end-to-end; used to identify crucial performance and basic functionality that will be run for every code check-in and commit; may launch or interact with services in a datacenter, preferably with a staging environment to avoid affecting production
    ```
    $ make large-tests
    ```

Continuous integration will run all of these tests either as pre-submits on PRs, post-submits against master/release branches, or both.

##### Documentation
We could always use improvements to our documentation! Anyone can contribute to these docs - whether you’re new to the project, you’ve been around a long time, and whether you self-identify as a developer, an end user, or someone who just can’t stand seeing typos. What exactly is needed?
1. More complementary documentation. Have you perhaps found something unclear?
2. More examples or generic templates that others can use.
3. Blog posts, articles and such – they’re all very appreciated.

You can also edit documentation files directly in the GitHub web interface, without creating a local copy. This can be convenient for small typos or grammer fixes.

## Maintainers

If you need help, feel free to tag one of the active maintainers of this project in a post or comment. We'll do our best to reach out to you as quickly as we can.

```
# Active maintainers marked with (*)

(*) Nelson Wang
(*) Tony Lee
(*) Brent Boe
(*) Matthew Rich
(*) Jonathan Vega
(*) Jack Meixensperger
(*) Brian Bingham
(*) Scott Centoni
(*) Mike Dickey
```
