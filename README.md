# 📦 AWS S3 Backup and Replication System

This project implements a fully automated backup and data redundancy solution using **Python** and **AWS Services (S3, Lambda, EventBridge)**.

>  **Project Title**: Automating File Backup and Ensuring Data Redundancy using AWS S3 and Replication  


---

> ⚠️ **Note**: This project does not have a live deployment due to AWS cost constraints. However, screenshots and a detailed report (`cloud-backup-aws.pdf`) are included.

---

## 🛠️ Tech Stack

- **Python 3.x** (Boto3 SDK, schedule, logging)
- **AWS S3** (Object storage)
- **AWS Lambda** (Replication logic)
- **AWS EventBridge** (Trigger automation)
- **AWS IAM** (Permissions and roles)
- **AWS CloudWatch Logs** (Monitoring)
- **GitHub** (Source control)

---


## 🚀 Features

- ⬆️ Automatically uploads files from local directories to an AWS S3 bucket
- 🔁 Replicates uploaded files to a second S3 bucket in the same region using Lambda
- 🕒 Periodic backups using built-in scheduler or Windows Task Scheduler
- ♻️ Retention policy to delete older backups
- 🔐 Secure with IAM roles and no hardcoded credentials
- 📄 Includes logging and timestamp-based folder structure

---

## 📂 Project Structure

```txt
aws-backup-replication/
├── backup_logic.py           # Local backup agent
├── lambda_replication.py     # AWS Lambda function code
├── backup_config.json        # Sample configuration file
├── cloud-backup-aws.pdf      # Detailed project methodology
├── requirements.txt          # Python dependencies
├── .gitignore                # Git ignore rules              
└── README.md                 # This file

```
---

📄 See cloud-backup-aws.pdf for complete documentation including:

- Project background and objectives
- Problem statement
- System architecture
- Technologies used
- Implementation details
- Screenshots
- Results and future scope

---

## 👩‍💻 Developed By

**Riddhi Shah**  
