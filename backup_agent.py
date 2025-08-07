#!/usr/bin/env python3
#python backup_agent.py --config backup_config.json


import os
import sys
import argparse
import json
import logging
import datetime
import hashlib
import boto3
from botocore.exceptions import ClientError
import time  
from pathlib import Path
import schedule
import time
import uuid
import hashlib

def job():
    try:
        args = parse_args()
        config = load_config(args)

        if 'bucket_name' not in config or 'source_paths' not in config:
            logger.error("Missing required configuration (bucket_name or source_paths)")
            return

        agent = BackupAgent(config)
        agent.run_backup()
    except Exception as e:
        logger.error(f"Scheduled backup failed: {str(e)}")
def get_mac_address():
    """Return the hardware MAC as a colon-separated hex string."""
    mac = uuid.getnode()
    return ':'.join(f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8))

def get_device_id():
    """
    Hash the MAC for privacy and fixed length.
    Returns a 16-char hex string unique to this machine.
    """
    raw_mac = get_mac_address()
    return hashlib.sha256(raw_mac.encode()).hexdigest()[:16]
    
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backup.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("backup-agent")

class BackupAgent:
    """Main class for handling file backups to AWS S3"""
    
    def __init__(self, config):
        """
        Initialize the backup agent with the provided configuration
        
        Args:
            config (dict): Configuration settings for the backup agent
        """
        self.config = config
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Verify required config parameters
        required_params = ['bucket_name', 'source_paths']
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Missing required configuration parameter: {param}")
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client('s3')
            logger.info(f"Successfully initialized S3 client")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise
        
        # Set defaults for optional parameters
        self.config.setdefault('retention_days', 7)
        self.config.setdefault('prefix', '')  # Optional prefix for S3 objects
    
    def run_backup(self):
        """
        Execute the full backup process:
        1. Collect files from source paths
        2. Upload files to S3
        3. Apply retention policy
        """
        logger.info(f"Starting backup process at {self.timestamp}")
        
        try:
            # Collect files to backup
            files_to_backup = self.collect_files()
            if not files_to_backup:
                logger.warning("No files found to backup")
                return
            
            logger.info(f"Found {len(files_to_backup)} files to backup")
            
            # Upload files to S3
            uploaded_files = self.upload_files(files_to_backup)
            
            # Apply retention policy
            if self.config.get('apply_retention', True):
                self.apply_retention_policy()
            
            logger.info(f"Backup completed successfully. Uploaded {len(uploaded_files)} files.")
            
        except Exception as e:
            logger.error(f"Backup process failed: {str(e)}")
            raise
    
    def collect_files(self):
        """
        Collect all files from the specified source paths
        
        Returns:
            list: List of file paths to be backed up
        """
        files_to_backup = []
        
        for source_path in self.config['source_paths']:
            source_path = os.path.abspath(os.path.expanduser(source_path))
            
            if not os.path.exists(source_path):
                logger.warning(f"Source path does not exist: {source_path}")
                continue
            
            logger.info(f"Collecting files from: {source_path}")
            
            if os.path.isfile(source_path):
                files_to_backup.append(source_path)
            elif os.path.isdir(source_path):
                # Walk through the directory
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        files_to_backup.append(file_path)
        
        return files_to_backup
    
    def upload_files(self, file_paths):
        """
        new code
        Upload all files, preserving their local names and folder structure,
        under my-backups/<user_id>/<timestamp>/...
        """
        uploaded_files = []
        total = len(file_paths)
        user_id = self.config.get('user_id')
        if not user_id:
            raise ValueError("Missing `user_id` in config")

        base_folder = f"{self.config.get('prefix', 'my-backups')}/{user_id}/{self.timestamp}"

        for idx, local_path in enumerate(file_paths, start=1):
            try:
                # Compute relative path under the source root
                root = os.path.commonprefix(self.config['source_paths'])
                rel = os.path.relpath(local_path, root).replace('\\', '/')

                # If relpath gives '.', replace with the filename itself
                if rel in ('.', ''):
                    rel = os.path.basename(local_path)

                # Final S3 key
                s3_key = f"{base_folder}/{rel}"

                logger.info(f"[{idx}/{total}] Uploading {local_path} → {s3_key}")
                self.s3_client.upload_file(local_path,
                                           self.config['bucket_name'],
                                           s3_key)
                uploaded_files.append(s3_key)

            except Exception as e:
                logger.error(f"Upload failed for {local_path}: {e}")

        return uploaded_files
    
    
    def apply_retention_policy(self):
        """
        new code
        Apply the configured retention policy by removing backups that are older than
        the specified retention period (days or minutes), scoped per user.
        """
        try:
            # Retrieve retention settings
            retention_days = self.config.get('retention_days', 0)
            retention_minutes = self.config.get('retention_minutes', 0)
            user_id = self.config.get('user_id')
            prefix = self.config.get('prefix', 'my-backups')

            if not user_id:
                logger.error("Missing `user_id` in config for retention")
                return

            # Determine cutoff timestamp
            if retention_days > 0:
                cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
                logger.info(f"Retention: keeping backups for {retention_days} days (cutoff={cutoff})")
            elif retention_minutes > 0:
                cutoff = datetime.datetime.now() - datetime.timedelta(minutes=retention_minutes)
                logger.info(f"Retention: keeping backups for {retention_minutes} minutes (cutoff={cutoff})")
            else:
                logger.info("Retention policy disabled, keeping all backups")
                return

            # Build the S3 key prefix for this user
            full_prefix = f"{prefix}/{user_id}/"
            paginator = self.s3_client.get_paginator('list_objects_v2')

            # Collect all keys to delete
            to_delete = []
            for page in paginator.paginate(Bucket=self.config['bucket_name'], Prefix=full_prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    # Strip off the user folder prefix, then split to get the timestamp folder
                    relative_path = key[len(full_prefix):]
                    parts = relative_path.split('/')
                    if not parts:
                        continue

                    ts_str = parts[0]  # timestamp folder name
                    try:
                        ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
                    except ValueError:
                        # Skip any keys not matching the timestamp format
                        continue

                    if ts < cutoff:
                        to_delete.append(key)

            if not to_delete:
                logger.info("No objects to delete for retention")
                return

            # Batch delete in up to 1000-key chunks
            deleted_count = 0
            for i in range(0, len(to_delete), 1000):
                batch = to_delete[i:i+1000]
                response = self.s3_client.delete_objects(
                    Bucket=self.config['bucket_name'],
                    Delete={'Objects': [{'Key': k} for k in batch], 'Quiet': False}
                )
                deleted = response.get('Deleted', [])
                deleted_count += len(deleted)

                # Log any errors returned
                for err in response.get('Errors', []):
                    logger.warning(f"Delete error {err['Key']}: {err['Code']} - {err['Message']}")

            logger.info(f"Retention policy applied: deleted {deleted_count} objects from old backups")

        except Exception as e:
            logger.error(f"Failed to apply retention policy: {e}")
    
def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Cloud Backup Agent")
    
    parser.add_argument('-c', '--config', dest='config_file',
                      help='Path to configuration file')
    
    parser.add_argument('-s', '--source', dest='source_paths', action='append',
                      help='Source paths to backup (can be specified multiple times)')
    
    parser.add_argument('-b', '--bucket', dest='bucket_name',
                      help='S3 bucket name for backup storage')
    
    parser.add_argument('-p', '--prefix', dest='prefix',
                      help='Prefix for S3 objects (e.g., "mybackups")')
    
    parser.add_argument('-rt', '--retentiond', dest='retention_days', type=int,
                      help='Number of days to keep backups (default: 7)')
    parser.add_argument('-rm', '--retentionm', dest='retention_minutes', type=int,
                      help='Number of minutes to keep backups (default: 0)')
    
    parser.add_argument('--no-retention', dest='apply_retention', action='store_false',
                      help='Disable retention policy')
    
    return parser.parse_args()


def load_config(args):
    """
    Load configuration from file and/or command line arguments
    
    Command line arguments take precedence over config file settings
    """
    config = {}
    
    # Load from config file if specified
    if args.config_file:
        try:
            with open(args.config_file, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
            logger.info(f"Loaded configuration from {args.config_file}")
        except Exception as e:
            logger.error(f"Failed to load config file: {str(e)}")
            sys.exit(1)
    
    # Override with command line arguments
    if args.source_paths:
        config['source_paths'] = args.source_paths
    
    if args.bucket_name:
        config['bucket_name'] = args.bucket_name
    
    if args.prefix is not None:
        config['prefix'] = args.prefix
    
    if args.retention_days is not None:
        config['retention_days'] = args.retention_days
    
    if args.apply_retention is not None:
        config['apply_retention'] = args.apply_retention
    
    return config


def main():
    """Main function to run the backup agent"""
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Load configuration
        config = load_config(args)
        
        # Generate and set the user_id automatically
        config['user_id'] = get_device_id()

        # Verify essential configuration
        if 'bucket_name' not in config:
            logger.error("No S3 bucket specified. Use --bucket or config file.")
            sys.exit(1)
        
        if 'source_paths' not in config or not config['source_paths']:
            logger.error("No source paths specified. Use --source or config file.")
            sys.exit(1)
        
        # Initialize and run backup agent
        agent = BackupAgent(config)
        #agent.run_backup()
        ######################################################################
         # Run the backup in a loop every minute
        while True:
            try:
                # Run the backup process
                agent.run_backup()
                
                # Wait for 1 minute before running the next backup
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Backup failed: {str(e)}")
                time.sleep(60)  # Wait before retrying on failure
#######################################################################
        
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
    