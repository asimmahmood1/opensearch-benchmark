# Licensed to Elasticsearch B.V. under one or more contributor
# license agreements. See the NOTICE file distributed with
# this work for additional information regarding copyright
# ownership. Elasticsearch B.V. licenses this file to you under
# the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import unittest.mock as mock
from unittest import TestCase

from esrally import exceptions, config
from esrally.mechanic import supplier, team


class RevisionExtractorTests(TestCase):
    def test_single_revision(self):
        self.assertDictEqual({"elasticsearch": "67c2f42", "all": "67c2f42"}, supplier._extract_revisions("67c2f42"))
        self.assertDictEqual({"elasticsearch": "current", "all": "current"}, supplier._extract_revisions("current"))
        self.assertDictEqual({"elasticsearch": "@2015-01-01-01:00:00", "all": "@2015-01-01-01:00:00"},
                             supplier._extract_revisions("@2015-01-01-01:00:00"))

    def test_multiple_revisions(self):
        self.assertDictEqual({"elasticsearch": "67c2f42", "x-pack": "@2015-01-01-01:00:00", "some-plugin": "current"},
                             supplier._extract_revisions("elasticsearch:67c2f42,x-pack:@2015-01-01-01:00:00,some-plugin:current"))

    def test_invalid_revisions(self):
        with self.assertRaises(exceptions.SystemSetupError) as ctx:
            supplier._extract_revisions("elasticsearch 67c2f42,x-pack:current")
        self.assertEqual("Revision [elasticsearch 67c2f42] does not match expected format [name:revision].", ctx.exception.args[0])


class SourceRepositoryTests(TestCase):
    @mock.patch("esrally.utils.git.head_revision", autospec=True)
    @mock.patch("esrally.utils.git.pull", autospec=True)
    @mock.patch("esrally.utils.git.clone", autospec=True)
    @mock.patch("esrally.utils.git.is_working_copy", autospec=True)
    def test_intial_checkout_latest(self, mock_is_working_copy, mock_clone, mock_pull, mock_head_revision):
        # before cloning, it is not a working copy, afterwards it is
        mock_is_working_copy.side_effect = [False, True]
        mock_head_revision.return_value = "HEAD"

        s = supplier.SourceRepository(name="Elasticsearch", remote_url="some-github-url", src_dir="/src")
        s.fetch("latest")

        mock_is_working_copy.assert_called_with("/src")
        mock_clone.assert_called_with("/src", "some-github-url")
        mock_pull.assert_called_with("/src")
        mock_head_revision.assert_called_with("/src")

    @mock.patch("esrally.utils.git.head_revision", autospec=True)
    @mock.patch("esrally.utils.git.pull")
    @mock.patch("esrally.utils.git.clone")
    @mock.patch("esrally.utils.git.is_working_copy", autospec=True)
    def test_checkout_current(self, mock_is_working_copy, mock_clone, mock_pull, mock_head_revision):
        mock_is_working_copy.return_value = True
        mock_head_revision.return_value = "HEAD"

        s = supplier.SourceRepository(name="Elasticsearch", remote_url="some-github-url", src_dir="/src")
        s.fetch("current")

        mock_is_working_copy.assert_called_with("/src")
        self.assertEqual(0, mock_clone.call_count)
        self.assertEqual(0, mock_pull.call_count)
        mock_head_revision.assert_called_with("/src")\


    @mock.patch("esrally.utils.git.head_revision", autospec=True)
    @mock.patch("esrally.utils.git.checkout")
    @mock.patch("esrally.utils.git.pull")
    @mock.patch("esrally.utils.git.clone")
    @mock.patch("esrally.utils.git.is_working_copy", autospec=True)
    def test_checkout_revision_for_local_only_repo(self, mock_is_working_copy, mock_clone, mock_pull, mock_checkout, mock_head_revision):
        mock_is_working_copy.return_value = True
        mock_head_revision.return_value = "HEAD"

        # local only, we dont specify a remote
        s = supplier.SourceRepository(name="Elasticsearch", remote_url=None, src_dir="/src")
        s.fetch("67c2f42")

        mock_is_working_copy.assert_called_with("/src")
        self.assertEqual(0, mock_clone.call_count)
        self.assertEqual(0, mock_pull.call_count)
        mock_checkout.assert_called_with("/src", "67c2f42")
        mock_head_revision.assert_called_with("/src")

    @mock.patch("esrally.utils.git.head_revision", autospec=True)
    @mock.patch("esrally.utils.git.pull_ts", autospec=True)
    @mock.patch("esrally.utils.git.is_working_copy", autospec=True)
    def test_checkout_ts(self, mock_is_working_copy, mock_pull_ts, mock_head_revision):
        mock_is_working_copy.return_value = True
        mock_head_revision.return_value = "HEAD"

        s = supplier.SourceRepository(name="Elasticsearch", remote_url="some-github-url", src_dir="/src")
        s.fetch("@2015-01-01-01:00:00")

        mock_is_working_copy.assert_called_with("/src")
        mock_pull_ts.assert_called_with("/src", "2015-01-01-01:00:00")
        mock_head_revision.assert_called_with("/src")

    @mock.patch("esrally.utils.git.head_revision", autospec=True)
    @mock.patch("esrally.utils.git.pull_revision", autospec=True)
    @mock.patch("esrally.utils.git.is_working_copy", autospec=True)
    def test_checkout_revision(self, mock_is_working_copy, mock_pull_revision, mock_head_revision):
        mock_is_working_copy.return_value = True
        mock_head_revision.return_value = "HEAD"

        s = supplier.SourceRepository(name="Elasticsearch", remote_url="some-github-url", src_dir="/src")
        s.fetch("67c2f42")

        mock_is_working_copy.assert_called_with("/src")
        mock_pull_revision.assert_called_with("/src", "67c2f42")
        mock_head_revision.assert_called_with("/src")

    def test_is_commit_hash(self):
        self.assertTrue(supplier.SourceRepository.is_commit_hash("67c2f42"))

    def test_is_not_commit_hash(self):
        self.assertFalse(supplier.SourceRepository.is_commit_hash("latest"))
        self.assertFalse(supplier.SourceRepository.is_commit_hash("current"))
        self.assertFalse(supplier.SourceRepository.is_commit_hash("@2015-01-01-01:00:00"))


class BuilderTests(TestCase):
    @mock.patch("esrally.utils.process.run_subprocess")
    @mock.patch("esrally.utils.jvm.major_version")
    def test_build_on_jdk_8(self, jvm_major_version, mock_run_subprocess):
        jvm_major_version.return_value = 8
        mock_run_subprocess.return_value = False

        b = supplier.Builder(src_dir="/src", java_home="/opt/jdk8", log_dir="logs")
        b.build(["./gradlew clean", "./gradlew assemble"])

        calls = [
            # Actual call
            mock.call("export JAVA_HOME=/opt/jdk8; cd /src; ./gradlew clean > logs/build.log 2>&1"),
            # Return value check
            mock.call("export JAVA_HOME=/opt/jdk8; cd /src; ./gradlew assemble > logs/build.log 2>&1"),
        ]

        mock_run_subprocess.assert_has_calls(calls)

    @mock.patch("esrally.utils.process.run_subprocess")
    @mock.patch("esrally.utils.jvm.major_version")
    def test_build_on_jdk_10(self, jvm_major_version, mock_run_subprocess):
        jvm_major_version.return_value = 10
        mock_run_subprocess.return_value = False

        b = supplier.Builder(src_dir="/src", java_home="/opt/jdk10", log_dir="logs")
        b.build(["./gradlew clean", "./gradlew assemble"])

        calls = [
            # Actual call
            mock.call("export JAVA_HOME=/opt/jdk10; cd /src; ./gradlew clean > logs/build.log 2>&1"),
            # Return value check
            mock.call("export JAVA_HOME=/opt/jdk10; cd /src; ./gradlew assemble > logs/build.log 2>&1"),
        ]

        mock_run_subprocess.assert_has_calls(calls)


class TemplateRendererTests(TestCase):
    def test_uses_provided_values(self):
        renderer = supplier.TemplateRenderer(version="1.2.3", os_name="Windows", arch="arm7")
        self.assertEqual("This is version 1.2.3 on Windows with a arm7 CPU.",
                         renderer.render("This is version {{VERSION}} on {{OSNAME}} with a {{ARCH}} CPU."))

    @mock.patch("esrally.utils.sysstats.os_name", return_value="Linux")
    @mock.patch("esrally.utils.sysstats.cpu_arch", return_value="X86_64")
    def test_uses_derived_values(self, os_name, cpu_arch):
        renderer = supplier.TemplateRenderer(version="1.2.3")
        self.assertEqual("This is version 1.2.3 on linux with a x86_64 CPU.",
                         renderer.render("This is version {{VERSION}} on {{OSNAME}} with a {{ARCH}} CPU."))


class ElasticsearchSourceSupplierTests(TestCase):
    def test_no_build(self):
        car = team.Car("default", root_path=None, config_paths=[], variables={
            "clean_command": "./gradlew clean",
            "system.build_command": "./gradlew assemble"
        })
        renderer = supplier.TemplateRenderer(version=None)
        es = supplier.ElasticsearchSourceSupplier(revision="abc",
                                                  es_src_dir="/src",
                                                  remote_url="",
                                                  car=car,
                                                  builder=None,
                                                  template_renderer=renderer)
        es.prepare()
        # nothing has happened (intentionally) because there is no builder

    def test_build(self):
        car = team.Car("default", root_path=None, config_paths=[], variables={
            "clean_command": "./gradlew clean",
            "system.build_command": "./gradlew assemble"
        })
        builder = mock.create_autospec(supplier.Builder)
        renderer = supplier.TemplateRenderer(version="abc")
        es = supplier.ElasticsearchSourceSupplier(revision="abc",
                                                  es_src_dir="/src",
                                                  remote_url="",
                                                  car=car,
                                                  builder=builder,
                                                  template_renderer=renderer)
        es.prepare()

        builder.build.assert_called_once_with(["./gradlew clean", "./gradlew assemble"])

    def test_raises_error_on_missing_car_variable(self):
        car = team.Car("default", root_path=None, config_paths=[], variables={
            "clean_command": "./gradlew clean",
            # system.build_command is not defined
        })
        renderer = supplier.TemplateRenderer(version="abc")
        builder = mock.create_autospec(supplier.Builder)
        es = supplier.ElasticsearchSourceSupplier(revision="abc",
                                                  es_src_dir="/src",
                                                  remote_url="",
                                                  car=car,
                                                  builder=builder,
                                                  template_renderer=renderer)
        with self.assertRaisesRegex(exceptions.SystemSetupError,
                                    "Car \"default\" requires config key \"system.build_command\"."):
            es.prepare()

        self.assertEqual(0, builder.build.call_count)

    @mock.patch("glob.glob", lambda p: ["elasticsearch.tar.gz"])
    def test_add_elasticsearch_binary(self):
        car = team.Car("default", root_path=None, config_paths=[], variables={
            "clean_command": "./gradlew clean",
            "system.build_command": "./gradlew assemble",
            "system.artifact_path_pattern": "distribution/archives/tar/build/distributions/*.tar.gz"
        })
        renderer = supplier.TemplateRenderer(version="abc")
        es = supplier.ElasticsearchSourceSupplier(revision="abc",
                                                  es_src_dir="/src",
                                                  remote_url="",
                                                  car=car,
                                                  builder=None,
                                                  template_renderer=renderer)
        binaries = {}
        es.add(binaries=binaries)
        self.assertEqual(binaries, {"elasticsearch": "elasticsearch.tar.gz"})


class ExternalPluginSourceSupplierTests(TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.along_es = None
        self.standalone = None

    def setUp(self):
        self.along_es = supplier.ExternalPluginSourceSupplier(plugin=team.PluginDescriptor("some-plugin", core_plugin=False),
                                                              revision="abc",
                                                              # built along-side ES
                                                              src_dir="/src",
                                                              src_config={
                                                                  "plugin.some-plugin.src.subdir": "elasticsearch-extra/some-plugin",
                                                                  "plugin.some-plugin.build.artifact.subdir": "plugin/build/distributions"
                                                              },
                                                              builder=None)

        self.standalone = supplier.ExternalPluginSourceSupplier(plugin=team.PluginDescriptor("some-plugin", core_plugin=False),
                                                                revision="abc",
                                                                # built separately
                                                                src_dir=None,
                                                                src_config={
                                                                    "plugin.some-plugin.src.dir": "/Projects/src/some-plugin",
                                                                    "plugin.some-plugin.build.artifact.subdir": "build/distributions"
                                                                },
                                                                builder=None)

    def test_invalid_config_no_source(self):
        with self.assertRaisesRegex(exceptions.SystemSetupError,
                                    "Neither plugin.some-plugin.src.dir nor plugin.some-plugin.src.subdir are set for plugin some-plugin."):
            supplier.ExternalPluginSourceSupplier(plugin=team.PluginDescriptor("some-plugin", core_plugin=False),
                                                  revision="abc",
                                                  # built separately
                                                  src_dir=None,
                                                  src_config={
                                                      # but no source config
                                                      # "plugin.some-plugin.src.dir": "/Projects/src/some-plugin",
                                                      "plugin.some-plugin.build.artifact.subdir": "build/distributions"
                                                  },
                                                  builder=None)

    def test_invalid_config_duplicate_source(self):
        with self.assertRaisesRegex(exceptions.SystemSetupError,
                                    "Can only specify one of plugin.duplicate.src.dir and plugin.duplicate.src.subdir but both are set."):
            supplier.ExternalPluginSourceSupplier(plugin=team.PluginDescriptor("duplicate", core_plugin=False),
                                                  revision="abc",
                                                  src_dir=None,
                                                  src_config={
                                                      "plugin.duplicate.src.subdir": "elasticsearch-extra/some-plugin",
                                                      "plugin.duplicate.src.dir": "/Projects/src/some-plugin",
                                                      "plugin.duplicate.build.artifact.subdir": "build/distributions"
                                                  },
                                                  builder=None)

    def test_standalone_plugin_overrides_build_dir(self):
        self.assertEqual("/Projects/src/some-plugin", self.standalone.override_build_dir)

    def test_along_es_plugin_keeps_build_dir(self):
        self.assertIsNone(self.along_es.override_build_dir)

    @mock.patch("glob.glob", lambda p: ["/src/elasticsearch-extra/some-plugin/plugin/build/distributions/some-plugin.zip"])
    def test_add_binary_built_along_elasticsearch(self):
        binaries = {}
        self.along_es.add(binaries)
        self.assertDictEqual(binaries,
                             {"some-plugin": "file:///src/elasticsearch-extra/some-plugin/plugin/build/distributions/some-plugin.zip"})

    @mock.patch("glob.glob", lambda p: ["/Projects/src/some-plugin/build/distributions/some-plugin.zip"])
    def test_resolve_plugin_binary_built_standalone(self):
        binaries = {}
        self.along_es.add(binaries)
        self.assertDictEqual(binaries,
                             {"some-plugin": "file:///Projects/src/some-plugin/build/distributions/some-plugin.zip"})


class CorePluginSourceSupplierTests(TestCase):
    @mock.patch("glob.glob", lambda p: ["/src/elasticsearch/core-plugin/build/distributions/core-plugin.zip"])
    def test_resolve_plugin_binary(self):
        s = supplier.CorePluginSourceSupplier(plugin=team.PluginDescriptor("core-plugin", core_plugin=True),
                                              # built separately
                                              es_src_dir="/src/elasticsearch",
                                              builder=None)
        binaries = {}
        s.add(binaries)
        self.assertDictEqual(binaries, {"core-plugin": "file:///src/elasticsearch/core-plugin/build/distributions/core-plugin.zip"})


class PluginDistributionSupplierTests(TestCase):
    def test_resolve_plugin_url(self):
        v = {"plugin_custom-analyzer_release_url": "http://example.org/elasticearch/custom-analyzer-{{VERSION}}.zip"}
        renderer = supplier.TemplateRenderer(version="6.3.0")
        s = supplier.PluginDistributionSupplier(repo=supplier.DistributionRepository(name="release",
                                                                                     distribution_config=v,
                                                                                     template_renderer=renderer),
                                                plugin=team.PluginDescriptor("custom-analyzer"))
        binaries = {}
        s.add(binaries)
        self.assertDictEqual(binaries, {"custom-analyzer": "http://example.org/elasticearch/custom-analyzer-6.3.0.zip"})


class CreateSupplierTests(TestCase):
    def test_derive_supply_requirements_es_source_build(self):
        # corresponds to --revision="abc"
        requirements = supplier._supply_requirements(
            sources=True, distribution=False, build=True, plugins=[], revisions={"elasticsearch": "abc"}, distribution_version=None)
        self.assertDictEqual({"elasticsearch": ("source", "abc", True)}, requirements)

    def test_derive_supply_requirements_es_source_skip(self):
        # corresponds to --pipeline=from-sources-skip-build
        requirements = supplier._supply_requirements(
            sources=True, distribution=False, build=False, plugins=[], revisions={"elasticsearch": "current"}, distribution_version=None)
        self.assertDictEqual({"elasticsearch": ("source", "current", False)}, requirements)

    def test_derive_supply_requirements_es_distribution(self):
        # corresponds to --distribution-version=6.0.0
        requirements = supplier._supply_requirements(
            sources=False, distribution=True, build=False, plugins=[], revisions={}, distribution_version="6.0.0")
        self.assertDictEqual({"elasticsearch": ("distribution", "6.0.0", False)}, requirements)

    def test_derive_supply_requirements_es_and_plugin_source_build(self):
        # corresponds to --revision="elasticsearch:abc,community-plugin:effab"
        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False)

        requirements = supplier._supply_requirements(sources=True, distribution=False, build=True, plugins=[core_plugin, external_plugin],
                                                     revisions={"elasticsearch": "abc", "all": "abc", "community-plugin": "effab"},
                                                     distribution_version=None)
        self.assertDictEqual({
            "elasticsearch": ("source", "abc", True),
            # core plugin configuration is forced to be derived from ES
            "analysis-icu": ("source", "abc", True),
            "community-plugin": ("source", "effab", True),
        }, requirements)

    def test_derive_supply_requirements_es_distribution_and_plugin_source_build(self):
        # corresponds to --revision="community-plugin:effab" --distribution-version="6.0.0"
        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False)

        requirements = supplier._supply_requirements(sources=False, distribution=True, build=False, plugins=[core_plugin, external_plugin],
                                                     revisions={"community-plugin": "effab"},
                                                     distribution_version="6.0.0")
        # core plugin is not contained, its configured is forced to be derived by ES
        self.assertDictEqual({
            "elasticsearch": ("distribution", "6.0.0", False),
            # core plugin configuration is forced to be derived from ES
            "analysis-icu": ("distribution", "6.0.0", False),
            "community-plugin": ("source", "effab", True),
        }, requirements)

    def test_derive_supply_requirements_es_distribution_and_plugin_source_skip(self):
        # corresponds to --from-sources-skip-build --revision="community-plugin:current" --distribution-version="6.0.0"
        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False)

        requirements = supplier._supply_requirements(sources=True, distribution=False, build=False, plugins=[core_plugin, external_plugin],
                                                     revisions={"community-plugin": "current"},
                                                     distribution_version="6.0.0")
        self.assertDictEqual({
            "elasticsearch": ("distribution", "6.0.0", False),
            # core plugin configuration is forced to be derived from ES
            "analysis-icu": ("distribution", "6.0.0", False),
            "community-plugin": ("source", "current", False),
        }, requirements)

    def test_create_suppliers_for_es_only_config(self):
        cfg = config.Config()
        cfg.add(config.Scope.application, "mechanic", "distribution.version", "6.0.0")
        # default value from command line
        cfg.add(config.Scope.application, "mechanic", "source.revision", "current")
        cfg.add(config.Scope.application, "mechanic", "distribution.repository", "release")
        cfg.add(config.Scope.application, "distributions", "release.url",
                "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz")
        cfg.add(config.Scope.application, "distributions", "release.cache", True)
        cfg.add(config.Scope.application, "node", "root.dir", "/opt/rally")

        car = team.Car("default", root_path=None, config_paths=[])

        composite_supplier = supplier.create(cfg, sources=False, distribution=True, build=False, car=car)

        self.assertEqual(1, len(composite_supplier.suppliers))
        self.assertIsInstance(composite_supplier.suppliers[0], supplier.ElasticsearchDistributionSupplier)

    def test_create_suppliers_for_es_distribution_plugin_source_skip(self):
        cfg = config.Config()
        cfg.add(config.Scope.application, "mechanic", "distribution.version", "6.0.0")
        # default value from command line
        cfg.add(config.Scope.application, "mechanic", "source.revision", "community-plugin:current")
        cfg.add(config.Scope.application, "mechanic", "distribution.repository", "release")
        cfg.add(config.Scope.application, "distributions", "release.url",
                "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz")
        cfg.add(config.Scope.application, "distributions", "release.cache", True)
        cfg.add(config.Scope.application, "node", "root.dir", "/opt/rally")
        cfg.add(config.Scope.application, "source", "plugin.community-plugin.src.dir", "/home/user/Projects/community-plugin")

        car = team.Car("default", root_path=None, config_paths=[])
        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False, variables={"enabled": True})

        # --pipeline=from-sources-skip-build
        composite_supplier = supplier.create(cfg, sources=True, distribution=False, build=False, car=car, plugins=[
            core_plugin,
            external_plugin
        ])

        self.assertEqual(3, len(composite_supplier.suppliers))
        self.assertIsInstance(composite_supplier.suppliers[0], supplier.ElasticsearchDistributionSupplier)
        self.assertIsInstance(composite_supplier.suppliers[1], supplier.PluginDistributionSupplier)
        self.assertEqual(core_plugin, composite_supplier.suppliers[1].plugin)
        self.assertIsInstance(composite_supplier.suppliers[2], supplier.ExternalPluginSourceSupplier)
        self.assertEqual(external_plugin, composite_supplier.suppliers[2].plugin)
        self.assertIsNone(composite_supplier.suppliers[2].builder)

    def test_create_suppliers_for_es_missing_distribution_plugin_source_skip(self):
        cfg = config.Config()
        # no distribution version!
        # cfg.add(config.Scope.application, "mechanic", "distribution.version", "")
        # default value from command line
        cfg.add(config.Scope.application, "mechanic", "source.revision", "community-plugin:current")
        cfg.add(config.Scope.application, "mechanic", "distribution.repository", "release")
        cfg.add(config.Scope.application, "distributions", "release.url",
                "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz")
        cfg.add(config.Scope.application, "distributions", "release.cache", True)
        cfg.add(config.Scope.application, "node", "root.dir", "/opt/rally")

        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False)

        car = team.Car("default", root_path=None, config_paths=[])

        # --from-sources-skip-build --revision="community-plugin:current" (distribution version is missing!)
        with self.assertRaises(exceptions.SystemSetupError) as ctx:
            supplier.create(cfg, sources=True, distribution=False, build=False, car=car, plugins=[
                core_plugin,
                external_plugin
            ])
        self.assertRegex(ctx.exception.args[0], r"Could not determine version..*")

    @mock.patch("esrally.utils.jvm.resolve_path", lambda v: (v, "/opt/java/java{}".format(v)))
    def test_create_suppliers_for_es_distribution_plugin_source_build(self):
        cfg = config.Config()
        cfg.add(config.Scope.application, "mechanic", "distribution.version", "6.0.0")
        # default value from command line
        cfg.add(config.Scope.application, "mechanic", "source.revision", "community-plugin:current")
        cfg.add(config.Scope.application, "mechanic", "distribution.repository", "release")
        cfg.add(config.Scope.application, "distributions", "release.url",
                "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz")
        cfg.add(config.Scope.application, "distributions", "release.cache", True)
        cfg.add(config.Scope.application, "node", "root.dir", "/opt/rally")
        cfg.add(config.Scope.application, "node", "src.root.dir", "/opt/rally/src")
        cfg.add(config.Scope.application, "source", "elasticsearch.src.subdir", "elasticsearch")
        cfg.add(config.Scope.application, "source", "plugin.community-plugin.src.dir", "/home/user/Projects/community-plugin")

        car = team.Car("default", root_path=None, config_paths=[], variables={"build.jdk": "10"})
        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False)

        # --revision="community-plugin:effab" --distribution-version="6.0.0"
        composite_supplier = supplier.create(cfg, sources=False, distribution=True, build=False, car=car, plugins=[
            core_plugin,
            external_plugin
        ])

        self.assertEqual(3, len(composite_supplier.suppliers))
        self.assertIsInstance(composite_supplier.suppliers[0], supplier.ElasticsearchDistributionSupplier)
        self.assertIsInstance(composite_supplier.suppliers[1], supplier.PluginDistributionSupplier)
        self.assertEqual(core_plugin, composite_supplier.suppliers[1].plugin)
        self.assertIsInstance(composite_supplier.suppliers[2], supplier.ExternalPluginSourceSupplier)
        self.assertEqual(external_plugin, composite_supplier.suppliers[2].plugin)
        self.assertIsNotNone(composite_supplier.suppliers[2].builder)

    @mock.patch("esrally.utils.jvm.resolve_path", lambda v: (v, "/opt/java/java{}".format(v)))
    def test_create_suppliers_for_es_and_plugin_source_build(self):
        cfg = config.Config()
        cfg.add(config.Scope.application, "mechanic", "source.revision", "elasticsearch:abc,community-plugin:current")
        cfg.add(config.Scope.application, "mechanic", "distribution.repository", "release")
        cfg.add(config.Scope.application, "distributions", "release.url",
                "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz")
        cfg.add(config.Scope.application, "distributions", "release.cache", True)
        cfg.add(config.Scope.application, "node", "root.dir", "/opt/rally")
        cfg.add(config.Scope.application, "node", "src.root.dir", "/opt/rally/src")
        cfg.add(config.Scope.application, "source", "elasticsearch.src.subdir", "elasticsearch")
        cfg.add(config.Scope.application, "source", "remote.repo.url", "https://github.com/elastic/elasticsearch.git")
        cfg.add(config.Scope.application, "source", "plugin.community-plugin.src.subdir", "elasticsearch-extra/community-plugin")

        car = team.Car("default", root_path=None, config_paths=[], variables={
            "clean_command": "./gradlew clean",
            "build_command": "./gradlew assemble",
            "build.jdk": "11"
        })
        core_plugin = team.PluginDescriptor("analysis-icu", core_plugin=True)
        external_plugin = team.PluginDescriptor("community-plugin", core_plugin=False)

        # --revision="elasticsearch:abc,community-plugin:effab"
        composite_supplier = supplier.create(cfg, sources=True, distribution=False, build=True, car=car, plugins=[
            core_plugin,
            external_plugin
        ])

        self.assertEqual(3, len(composite_supplier.suppliers))
        self.assertIsInstance(composite_supplier.suppliers[0], supplier.ElasticsearchSourceSupplier)
        self.assertIsInstance(composite_supplier.suppliers[1], supplier.CorePluginSourceSupplier)
        self.assertEqual(core_plugin, composite_supplier.suppliers[1].plugin)
        self.assertIsInstance(composite_supplier.suppliers[2], supplier.ExternalPluginSourceSupplier)
        self.assertEqual(external_plugin, composite_supplier.suppliers[2].plugin)
        self.assertIsNotNone(composite_supplier.suppliers[2].builder)


class DistributionRepositoryTests(TestCase):
    @mock.patch("esrally.utils.sysstats.os_name", return_value="Linux")
    @mock.patch("esrally.utils.sysstats.cpu_arch", return_value="X86_64")
    def test_release_repo_config_with_default_url(self, os_name, cpu_arch):
        renderer = supplier.TemplateRenderer(version="7.3.2")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "runtime.jdk.bundled": "true",
            "jdk.bundled.release_url":
                "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}-{{OSNAME}}-{{ARCH}}.tar.gz",
            "release.cache": "true"
        }, template_renderer=renderer)
        self.assertEqual("https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-7.3.2-linux-x86_64.tar.gz", repo.download_url)
        self.assertEqual("elasticsearch-7.3.2-linux-x86_64.tar.gz", repo.file_name)
        self.assertTrue(repo.cache)

    def test_release_repo_config_with_user_url(self):
        renderer = supplier.TemplateRenderer(version="2.4.3")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "jdk.unbundled.release_url": "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz",
            "runtime.jdk.bundled": "false",
            # user override
            "release.url": "https://es-mirror.example.org/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz",
            "release.cache": "false"
        }, template_renderer=renderer)
        self.assertEqual("https://es-mirror.example.org/downloads/elasticsearch/elasticsearch-2.4.3.tar.gz", repo.download_url)
        self.assertEqual("elasticsearch-2.4.3.tar.gz", repo.file_name)
        self.assertFalse(repo.cache)

    def test_missing_url(self):
        renderer = supplier.TemplateRenderer(version="2.4.3")
        repo = supplier.DistributionRepository(name="miss", distribution_config={
            "jdk.unbundled.release_url": "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz",
            "runtime.jdk.bundled": "false",
            "release.cache": "true"
        }, template_renderer=renderer)
        with self.assertRaises(exceptions.SystemSetupError) as ctx:
            # noinspection PyStatementEffect
            repo.download_url
        self.assertEqual("Neither config key [miss.url] nor [jdk.unbundled.miss_url] is defined.", ctx.exception.args[0])

    def test_missing_cache(self):
        renderer = supplier.TemplateRenderer(version="2.4.3")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "jdk.unbundled.release.url": "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz",
            "runtime.jdk.bundled": "false"
        }, template_renderer=renderer)
        with self.assertRaises(exceptions.SystemSetupError) as ctx:
            # noinspection PyStatementEffect
            repo.cache
        self.assertEqual("Mandatory config key [release.cache] is undefined.", ctx.exception.args[0])

    def test_invalid_cache_value(self):
        renderer = supplier.TemplateRenderer(version="2.4.3")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "jdk.unbundled.release.url": "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-{{VERSION}}.tar.gz",
            "runtime.jdk.bundled": "false",
            "release.cache": "Invalid"
        }, template_renderer=renderer)
        with self.assertRaises(exceptions.SystemSetupError) as ctx:
            # noinspection PyStatementEffect
            repo.cache
        self.assertEqual("Value [Invalid] for config key [release.cache] is not a valid boolean value.", ctx.exception.args[0])

    def test_plugin_config_with_default_url(self):
        renderer = supplier.TemplateRenderer(version="5.5.0")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "runtime.jdk.bundled": "false",
            "plugin_example_release_url": "https://artifacts.example.org/downloads/plugins/example-{{VERSION}}.zip"
        }, template_renderer=renderer)
        self.assertEqual("https://artifacts.example.org/downloads/plugins/example-5.5.0.zip", repo.plugin_download_url("example"))

    def test_plugin_config_with_user_url(self):
        renderer = supplier.TemplateRenderer(version="5.5.0")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "runtime.jdk.bundled": "false",
            "plugin_example_release_url": "https://artifacts.example.org/downloads/plugins/example-{{VERSION}}.zip",
            # user override
            "plugin.example.release.url": "https://mirror.example.org/downloads/plugins/example-{{VERSION}}.zip"
        }, template_renderer=renderer)
        self.assertEqual("https://mirror.example.org/downloads/plugins/example-5.5.0.zip", repo.plugin_download_url("example"))

    def test_missing_plugin_config(self):
        renderer = supplier.TemplateRenderer(version="5.5.0")
        repo = supplier.DistributionRepository(name="release", distribution_config={
            "runtime.jdk.bundled": "false",
        }, template_renderer=renderer)
        self.assertIsNone(repo.plugin_download_url("not existing"))
