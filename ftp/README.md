# FTP intake (V0)

One **virtual FTP user per event**. The photographer enters these credentials in
their camera's FTP settings; uploads land in that event's intake directory, which
the watcher observes.

## Path layout

```
{FTP_ROOT}/raw/{event_id}/<photo.jpg>
```

The API's `provision_event_ftp()` creates `raw/{event_id}/` at event creation.
The user is chrooted to its event directory, so one photographer can only write
to its own event.

## Local dev

`docker compose up ftp` starts vsftpd using [`vsftpd.conf`](./vsftpd.conf) and
shares the `ftpdata` volume with the watcher. To actually register a virtual
user you provide a small script and point the API at it:

```
FTP_PROVISION_SCRIPT=/path/to/add_vsftpd_user.sh
```

The script is called as `add_vsftpd_user.sh <username> <password> <home_dir>` and
is responsible for adding the user to vsftpd's virtual user database (e.g. a
Berkeley DB built with `db_load`, or PAM/pwdfile). Without it, provisioning still
creates the intake directory — enough to test the watcher by dropping files into
`raw/{event_id}/` or using an FTP client that writes into the shared volume.

## Production (AWS)

The V1/cloud equivalent is **AWS Transfer Family**: create one Transfer user per
event, scoped (via IAM/home-directory mappings) to the `raw/{event_id}/` prefix
in S3. The watcher is then replaced by an S3 event → SQS → worker trigger; the
rest of the pipeline is unchanged.
