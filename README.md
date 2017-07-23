# Linux Security Database (LSD)
LSD tracks the security status of software projects for various GNU/Linux distributions. This page contains project details and analysis results. Visit my [LSD GitHub repository](https://github.com/NicoHood/LSD) for the source code of this project.

This project is a work in progress and it is likely that the code and web pages change.

## What?
LSD is a software project which analyzes package data and stores it inside a database. The database is then queried for the analyzes data and results are represented in different diagrams.

LSD currently only supports the analysis of Arch Linux but will get extended with other operating systems soon. A general software knowledge database with information about available gpg signatures, https, bugtracker links, etc. will be created too.

## Why?
A secure operating system requires securely packaged software. In order to secure the packaging process upstream developers need to sign their sources with GPG and optimally provide then over an encrypted HTTPS connection.

A single tampered package can compromise the system, no matter if its just an icon theme or a core feature. The reason why the LSD project was started to track the current status of the package security of several distributions and improve it over time.

## Where?
The results of the analysis can be found on the pages below:

* Software (TODO)
* [Arch Linux](ArchLinux)
* More planned

## How?
The analysis is written in Python and available from the [LSD GitHub repository](https://github.com/NicoHood/LSD). Everything is described in detail there. Additional information about the security analysis of Arch Linux can be found in my paper (german), which is going to be published soon.

## I want to help!
Great! There are several options you can do:

* Request developers to sign their sources with GPG (or sign your own projects)
* [GPGit](https://github.com/NicoHood/gpgit) may help you with this process
* Test and report bugs about GPGit and LSD
* [Contact me](http://contact.nicohood.de) if you have any further suggestion or comment
* Donate me some money, so i can work more often on the projects. Please contact me.
