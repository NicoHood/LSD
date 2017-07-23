<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>

# Arch Linux

## Table of Content
- TOC
{:toc}

## Results

### General Criteria

| Rating    | Security            | Explanation                             |
|-----------|---------------------|-----------------------------------------|
| Excellent | Very secure         | Criteria is met optimal                 |
| High      | Secure              | Criteria is met                         |
| Mid       | Insufficient secure | Criteria is met partly                  |
| Low       | Insecure            | Criteria is no met                      |
| N/A       | Not rated           | Criteria is not available or irrelevant |

### GPG Key

| Rating    | Explanation                                     |
|-----------|-------------------------------------------------|
| Excellent | Only strong GPG keys used >= RSA4096 / ECC      |
| High      | Only secure GPG keys used >= RSA 2048           |
| Mid       | Insecure keys used < RSA 2048 or DSA or expired |
| Low       | No GPG keys used                                |
| N/A       | Only local/no sources used                      |

<br>
{% include_relative total_gpg_key_security.div %}
<br>
{% include_relative total_gpg_key_security_table.div %}
<br>
{% include_relative gpg_key_distribution.div %}

### GPG Signature

| Rating    | Explanation                                     |
|-----------|-------------------------------------------------|
| Excellent | Same as high + GPG Key excellent                |
| High      | All sources are signed (excluding local files)  |
| Mid       | Some sources are signed (excluding local files) |
| Low       | No sources are signed                           |
| N/A       | Only local/no sources used                      |

<br>
{% include_relative total_signature_security.div %}
<br>
{% include_relative total_signature_security_table.div %}

### HTTPS

| Rating    | Explanation                                    |
|-----------|------------------------------------------------|
| Excellent | Same as high + upstream URL HTTPS              |
| High      | All sources use HTTPS (excluding local files)  |
| Mid       | Some sources use HTTPS (excluding local files) |
| Low       | No sources use HTTPS                           |
| N/A       | Only local/no sources used                     |

<br>
{% include_relative total_https_security.div %}
<br>
{% include_relative total_https_security_table.div %}

### Hash

| Rating    | Explanation              |
|-----------|--------------------------|
| Excellent | SHA512/Whirlpool         |
| High      | SHA256/SHA384            |
| Mid       | MD5/SHA1                 |
| Low       | SKIP in archives         |
| N/A       | Only VCS/no sources used |

<br>
{% include_relative total_hash_security.div %}
<br>
{% include_relative total_hash_security_table.div %}

### Package

| Rating    | Explanation                  |
|-----------|------------------------------|
| Excellent | All criteria >= high         |
| High      | GPG key + signatures >= high |
| Mid       | HTTPS >= high                |
| Low       | Rest                         |
| N/A       | No sources used              |

<br>
{% include_relative total_package_security.div %}
<br>
{% include_relative total_package_security_table.div %}

## Threat Model
### GPG Key

### GPG Signature

### HTTPS

### Hash

### Package
