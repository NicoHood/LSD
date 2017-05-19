# Linux Security Database (LSD)
## The work on LSD will start once [GPGit 2.0.0](https://github.com/NicoHood/gpgit/pull/5) is fully released.

LSD tracks the security status of Linux projects of various Linux projects and distributions.
It identifies unsigned source archives as well as unused GPG signatures in packages.
The maintainers of projects with potential of improvements will be notified and requested to use GPG signatures.
[GPGit](https://github.com/NicoHood/gpgit) will help developers to get started with GPG source code signing.
All information will be tracked in a database for a continual analysis and improvment.

##### Per project analysis:
* Availability of GPG signatures
* Strength of GPG keys and signatures (RSA 4096 / SHA512)
* Availability of strong hashes (SHA512/256)
* Availability of HTTPS
* Security of the dowload server
* Link to bugtracker
* Notes
* Meta information (Name, Website, Mirrors, etc.)

##### Per package analysis:
* Usage of GPG signatures
* Usage of strong hashes (SHA512/256)
* Link to bugtracker
* Notes
* Meta information (Name, Version, Sources, etc.)

##### Supported distributions
* ArchLinux & Derivate (Manjaro, Parabola, Hyperbola)
* More planned
