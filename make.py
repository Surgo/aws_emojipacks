#!/usr/bin/env python

import logging
import os
import shutil
import tempfile
import zipfile
try:
    from urllib.parse import urljoin
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve
    from urlparse import urljoin

import yaml
from PIL import Image


logging.basicConfig(level=logging.INFO)


DIST_DIR = 'emojis'
AWS_ICON_DOWNLOAD_URL = 'https://media.amazonwebservices.com/AWS-Design/Arch-Center/17.1.19_Update/AWS_Simple_Icons_EPS-SVG_v17.1.19.zip'
BASE_URL = 'https://raw.githubusercontent.com/Surgo/aws_emojipacks/master/'
IGNORED_SERVICE_GROUPS = ('General', 'SDK')
ALLOW_CHILD_SERVICES = ('Kinesis', )
REPLACE_NAMES = {
    'ImportExportSnowball': 'Snowball',
    'ElasticLoadBalancing': 'ELB',
}
IGNORED_NAMES = (
    'DatabaseMigrationService',
    'Kinesis-enabledapp',
    'snapshot',
    'volume',
)


def cleanup_dist_dir(dist_dir):
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.mkdir(dist_dir)


def download_icons(icons_url, dist_path):
    dist_path, headers = urlretrieve(icons_url, filename=dist_path)
    logging.info("Download to: %s", dist_path)
    return dist_path


def get_friendly_name_from_filename(path):
    filename = os.path.basename(path)
    friendly_name, _ = os.path.splitext(filename)
    _, friendly_name = friendly_name.split('_', 1)
    friendly_name = friendly_name.replace('Amazon', '').replace('AWS', '')

    name_parts = friendly_name.split('_')
    if len(name_parts) >= 2:
        if name_parts[0] not in ALLOW_CHILD_SERVICES:
            return None
        friendly_name = name_parts[-1]

    if friendly_name in REPLACE_NAMES:
        friendly_name = REPLACE_NAMES[friendly_name]

    if friendly_name in IGNORED_NAMES:
        return None

    return friendly_name.lower()


def get_images_from_archive_file(archived_filename):
    with zipfile.ZipFile(archived_filename, 'r') as archived_file:
        for path in archived_file.namelist():
            path_parts = path.split(os.sep)
            if len(path_parts) != 3:
                continue

            base, group, filename = path_parts
            if not filename.endswith('.png'):
                continue

            if group in IGNORED_SERVICE_GROUPS:
                continue

            friendly_name = get_friendly_name_from_filename(filename)
            if not friendly_name:
                continue

            with archived_file.open(path) as image_file:
                yield Image.open(image_file), friendly_name


def emojinize_image(image):
    image.thumbnail((128, 128), Image.ANTIALIAS)
    return image


def download_and_save_icons(dist_dir):
    saved_icons = dict()

    temp_dir = tempfile.gettempdir()
    temp_path = download_icons(AWS_ICON_DOWNLOAD_URL, os.path.join(temp_dir, 'icons.zip'))

    for image, friendly_name in get_images_from_archive_file(temp_path):
        emoji_icon = emojinize_image(image)
        dist_path = os.path.join(
            dist_dir,
            '{name}.{ext}'.format(name=friendly_name, ext='png'),
        )
        emoji_icon.save(dist_path, 'PNG', optimize=True)
        logging.info("Save emoji: %s", dist_path)
        saved_icons[friendly_name] = dist_path
    return saved_icons


def generate_emojipacks_yaml_data(base_url, saved_icons, prefix=None):
    emoji_data = []
    for friendly_name, dist_path in saved_icons.items():
        emoji_data.append(
            dict(
                name=prefix and '{prefix}-{name}'.format(prefix=prefix, name=friendly_name) or friendly_name,
                src=urljoin(base_url, dist_path),
            ),
        )
    return dict(
        title="aws service icons",
        emojis=emoji_data,
    )


if __name__ == '__main__':
    cleanup_dist_dir(DIST_DIR)
    saved_icons = download_and_save_icons(DIST_DIR)
    for prefix in (None, 'aws'):
        emojipacks_yaml_data = generate_emojipacks_yaml_data(BASE_URL, saved_icons, prefix=prefix)
        yaml_filename = '{prefix}-emojipacks.yml'.format(prefix=prefix or 'noprefix')
        with (open(yaml_filename, 'w')) as yaml_file:
            yaml.dump(emojipacks_yaml_data, yaml_file, default_flow_style=False)
        logging.info("Save yaml: %s", yaml_filename)
