"""
Copyright (c) 2012-2019 RockStor, Inc. <http://rockstor.com>
This file is part of RockStor.
RockStor is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published
by the Free Software Foundation; either version 2 of the License,
or (at your option) any later version.
RockStor is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""
import unittest
from mock import patch

from system.pkg_mgmt import pkg_update_check, pkg_changelog, zypper_repos_list


class SystemPackageTests(unittest.TestCase):
    """
    The tests in this suite can be run via the following command:
    cd <root dir of rockstor ie /opt/rockstor-dev>
    ./bin/test --settings=test-settings -v 3 -p test_pkg_mgmt*
    """

    def setUp(self):
        self.patch_run_command = patch("system.pkg_mgmt.run_command")
        self.mock_run_command = self.patch_run_command.start()

        # We need to test the conditions of distro.id() returning one of:
        # rockstor, opensuse-leap, opensuse-tumbleweed
        self.patch_distro = patch("system.pkg_mgmt.distro")
        self.mock_distro = self.patch_distro.start()

        # Mock pkg_infos to return "" to simplify higher level testing.
        self.patch_pkg_infos = patch("system.pkg_mgmt.pkg_infos")
        self.mock_pkg_infos = self.patch_pkg_infos.start()
        self.mock_pkg_infos.return_value = ""

    def tearDown(self):
        patch.stopall()

    def test_pkg_changelog(self):
        """
        Test pkg_changelog, a package changelog (including update changes)
        parser and presenter
        :return:
        """
        # Example output form "yum changelog 1 sos.noarch" such as is executed
        # in pkg_changelog()
        out = [
            [
                "==================== Installed Packages ====================",  # noqa E501
                "sos-3.6-17.el7.centos.noarch             installed",  # noqa E501
                "* Tue Apr 23 05:00:00 2019 CentOS Sources <bugs@centos.org> - 3.6-17.el7.centos",  # noqa E501
                "- Roll in CentOS Branding",  # noqa E501
                ""  # noqa E501
                "==================== Available Packages ====================",  # noqa E501
                "sos-3.7-6.el7.centos.noarch              updates",  # noqa E501
                "* Tue Sep  3 05:00:00 2019 CentOS Sources <bugs@centos.org> - 3.7-6.el7.centos",  # noqa E501
                "- Roll in CentOS Branding",  # noqa E501
                "",  # noqa E501
                "changelog stats. 2 pkgs, 2 source pkgs, 2 changelogs",  # noqa E501
                "",  # noqa E501
            ]
        ]
        err = [[""]]
        rc = [0]
        expected_results = [
            {
                "available": "sos-3.7-6.el7.centos.noarch              updates[line]* Tue Sep  3 05:00:00 2019 CentOS Sources <bugs@centos.org> - 3.7-6.el7.centos[line]- Roll in CentOS Branding",  # noqa E501
                "description": "",
                "name": "fake",
                "installed": "sos-3.6-17.el7.centos.noarch             installed[line]* Tue Apr 23 05:00:00 2019 CentOS Sources <bugs@centos.org> - 3.6-17.el7.centos[line]- Roll in CentOS Branding",  # noqa E501
            }
        ]
        distro_id = ["rockstor"]
        #
        # TODO: add openSUSE Leap example output. But currently exactly the same
        #  command but no available is listed as yum knows only rockstor repos.
        #
        for o, e, r, expected, distro in zip(out, err, rc, expected_results, distro_id):
            self.mock_run_command.return_value = (o, e, r)
            returned = pkg_changelog("fake.123", distro)
            self.assertEqual(
                returned,
                expected,
                msg="Un-expected pkg_changelog() result:\n "
                "returned = ({}).\n "
                "expected = ({}).".format(returned, expected),
            )

    def test_pkg_update_check(self):
        """
        Test pkg_update_check() across distro.id values and consequently different
        output format of:
        distro.id = "rockstor" (CentOS) base
        yum check-update -q -x rock*
        and:
        output format of:
        distro.id = "opensuse-leap"
        zypper -q list-updates
        and:
        distro.id = "opensuse-tumbleweed"
        same command as for opensuse-leap
        """
        # Mock pkg_changelog to allow for isolated testing of yum_check
        self.patch_pkg_changelog = patch("system.pkg_mgmt.pkg_changelog")
        self.mock_pkg_changelog = self.patch_pkg_changelog.start()

        def fake_pkg_changelog(*args, **kwargs):
            """
            Stubbed out fake pkg_changelog to allow for isolation of caller
            N.B. currenlty only uses single package test data to simply dict
            comparisons, ie recersive dict sort othewise required.
            :param args:  
            :param kwargs:
            :return: Dict indexed by name=arg[0], installed, available, and description.
            last 3 are = [] unless arg[1] is not "rockstor" then available has different
            content.
            """
            pkg_info = {"name": args[0].split(".")[0]}
            pkg_info["installed"] = ""
            pkg_info["available"] = ""
            if args[1] != "rockstor":
                pkg_info[
                    "available"
                ] = "Version and changelog of update not available in openSUSE"
            pkg_info["description"] = ""
            return pkg_info

        self.mock_pkg_changelog.side_effect = fake_pkg_changelog

        # TODO: We need more example here of un-happy paths
        # zypper spaces in Repository name Example,
        out = [
            [
                "S | Repository             | Name                    | Current Version                       | Available Version                     | Arch  ",  # noqa E501
                "--+------------------------+-------------------------+---------------------------------------+---------------------------------------+-------",  # noqa E501
                "v | Main Update Repository | aaa_base                | 84.87+git20180409.04c9dae-lp151.5.3.1 | 84.87+git20180409.04c9dae-lp151.5.6.1 | x86_64",  # noqa E501
                "",
            ]
        ]
        expected_result = [
            [
                {
                    "available": "Version and changelog of update not available in openSUSE",
                    "description": "",
                    "name": "aaa_base",
                    "installed": "",
                }
            ]
        ]
        err = [[""]]
        rc = [0]
        dist_id = ["opensuse-tumbleweed"]
        #
        # zypper no spaces in Repository name Example,
        # actual Leap 15.0 but no-space repos also seen in other openSUSE variants.
        out.append(
            [
                "S | Repository                | Name                            | Current Version                             | Available Version                           | Arch",  # noqa E501
                "--+---------------------------+---------------------------------+---------------------------------------------+---------------------------------------------+-------",  # noqa E501
                "v | openSUSE-Leap-15.0-Update | NetworkManager                  | 1.10.6-lp150.4.6.1                          | 1.10.6-lp150.4.9.1                          | x86_64",  # noqa E501
                "",
            ]
        )
        expected_result.append(
            [
                {
                    "available": "Version and changelog of update not available in openSUSE",
                    "description": "",
                    "name": "NetworkManager",
                    "installed": "",
                }
            ]
        )
        err.append([""])
        rc.append(0)
        dist_id.append("opensuse-tumbleweed")
        #
        # CentOS yum output example, ie one clear line above.
        out.append(
            [
                "",
                "epel-release.noarch                                                                        7-12                                                                        epel",  # noqa E501
                "",
            ]
        )
        expected_result.append(
            [
                {
                    "available": "",
                    "description": "",
                    "name": "epel-release",
                    "installed": "",
                }
            ]
        )
        err.append([""])
        rc.append(100)
        dist_id.append("rockstor")
        #
        # When we have a poorly repo.
        #     '/usr/bin/zypper', '--non-interactive', '-q', 'list-updates']
        out.append(
            [
                "",
                "",
                "",
                "",
                "File 'repomd.xml' from repository 'Rockstor-Testing' is unsigned, continue? [yes/no] (no): no",  # noqa E501
                "Warning: Skipping repository 'Rockstor-Testing' because of the above error.",  # noqa E501
                "S | Repository             | Name                    | Current Version                       | Available Version                     | Arch  ",  # noqa E501
                "--+------------------------+-------------------------+---------------------------------------+---------------------------------------+-------",  # noqa E501
                "v | Main Update Repository | aaa_base                | 84.87+git20180409.04c9dae-lp151.5.3.1 | 84.87+git20180409.04c9dae-lp151.5.9.1 | x86_64",  # noqa E501
                "v | Main Update Repository | aaa_base-extras         | 84.87+git20180409.04c9dae-lp151.5.3.1 | 84.87+git20180409.04c9dae-lp151.5.9.1 | x86_64",  # noqa E501
                "v | Main Update Repository | apparmor-parser         | 2.12.2-lp151.3.2                      | 2.12.3-lp151.4.3.1                    | x86_64",  # noqa E501
                "v | Main Update Repository | bash                    | 4.4-lp151.9.53                        | 4.4-lp151.10.3.1                      | x86_64",  # noqa E501
                "",
            ]
        )
        expected_result.append(
            [
                {
                    "available": "Version and changelog of update not available in openSUSE",
                    "description": "",
                    "name": "aaa_base",
                    "installed": "",
                },
                {
                    "available": "Version and changelog of update not available in openSUSE",
                    "description": "",
                    "name": "aaa_base-extras",
                    "installed": "",
                },
                {
                    "available": "Version and changelog of update not available in openSUSE",
                    "description": "",
                    "name": "apparmor-parser",
                    "installed": "",
                },
                {
                    "available": "Version and changelog of update not available in openSUSE",
                    "description": "",
                    "name": "bash",
                    "installed": "",
                },
            ]
        )
        err.append(
            [
                "Repository 'Rockstor-Testing' is invalid.",
                "[Rockstor-Testing|http://updates.rockstor.com:8999/rockstor-testing/leap/15.1] Valid metadata not found at specified URL",  # noqa E501
                "Some of the repositories have not been refreshed because of an error.",  # noqa E501
                "",
            ]
        )
        rc.append(106)
        dist_id.append("opensuse-leap")
        #
        for o, e, r, expected, distro in zip(out, err, rc, expected_result, dist_id):
            self.mock_run_command.return_value = (o, e, r)
            self.mock_distro.id.return_value = distro
            returned = pkg_update_check()
            self.assertEqual(
                returned,
                expected,
                msg="Un-expected yum_check() result:\n "
                "returned = ({}).\n "
                "expected = ({}).".format(returned, expected),
            )

    def test_zypper_repos_list(self):
        # Test empty return values
        out = [[""]]
        err = [[""]]
        rc = [0]
        expected_results = [[]]
        # test typical output
        out.append(
            [
                "",
                "#  | Alias                     | Name                               | Enabled | GPG Check | Refresh",  # noqa E501
                "---+---------------------------+------------------------------------+---------+-----------+--------",  # noqa E501
                " 1 | Local-Repository          | Local-Repository                   | Yes     | ( p) Yes  | Yes    ",  # noqa E501
                " 2 | Rockstor-Testing          | Rockstor-Testing                   | Yes     | ( p) Yes  | Yes    ",  # noqa E501
                " 3 | illuusio                  | illuusio                           | Yes     | (r ) Yes  | Yes    ",  # noqa E501
                " 4 | repo-debug                | Debug Repository                   | No      | ----      | ----   ",  # noqa E501
                " 5 | repo-debug-non-oss        | Debug Repository (Non-OSS)         | No      | ----      | ----   ",  # noqa E501
                " 6 | repo-debug-update         | Update Repository (Debug)          | No      | ----      | ----   ",  # noqa E501
                " 7 | repo-debug-update-non-oss | Update Repository (Debug, Non-OSS) | No      | ----      | ----   ",  # noqa E501
                " 8 | repo-non-oss              | Non-OSS Repository                 | Yes     | (r ) Yes  | No     ",  # noqa E501
                " 9 | repo-oss                  | Main Repository                    | Yes     | (r ) Yes  | No     ",  # noqa E501
                "10 | repo-source               | Source Repository                  | No      | ----      | ----   ",  # noqa E501
                "11 | repo-source-non-oss       | Source Repository (Non-OSS)        | No      | ----      | ----   ",  # noqa E501
                "12 | repo-update               | Main Update Repository             | Yes     | (r ) Yes  | No     ",  # noqa E501
                "13 | repo-update-non-oss       | Update Repository (Non-Oss)        | Yes     | (r ) Yes  | No     ",  # noqa E501
                "",
            ]
        )
        err.append([""])
        rc.append(0)
        expected_results.append(
            [
                "Local-Repository",
                "Rockstor-Testing",
                "illuusio",
                "repo-debug",
                "repo-debug-non-oss",
                "repo-debug-update",
                "repo-debug-update-non-oss",
                "repo-non-oss",
                "repo-oss",
                "repo-source",
                "repo-source-non-oss",
                "repo-update",
                "repo-update-non-oss",
            ]
        )

        for o, e, r, expected in zip(out, err, rc, expected_results):
            self.mock_run_command.return_value = (o, e, r)
            returned = zypper_repos_list()
            self.assertEqual(
                returned,
                expected,
                msg="Un-expected zypper_repos_list() result:\n "
                "returned = ({}).\n "
                "expected = ({}).".format(returned, expected),
            )