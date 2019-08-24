from os import makedirs
from os.path import join, exists, isdir
from re import sub
from tempfile import TemporaryDirectory

from tests.base import TestCase, assets, main, copy_of_directory

from ocrd.resolver import Resolver
from ocrd_utils import pushd_popd
#  setOverrideLogLevel('DEBUG')

TMP_FOLDER = '/tmp/test-core-resolver'
METS_HEROLD = assets.url_of('SBB0000F29300010000/data/mets.xml')
FOLDER_KANT = assets.path_to('kant_aufklaerung_1784')

# pylint: disable=redundant-unittest-assert, broad-except, deprecated-method, too-many-public-methods

class TestResolver(TestCase):

    def setUp(self):
        self.resolver = Resolver()
        if not isdir(TMP_FOLDER):
            makedirs(TMP_FOLDER)

    def test_workspace_from_url_bad(self):
        with self.assertRaisesRegex(Exception, "Must pass mets_url and/or baseurl"):
            self.resolver.workspace_from_url(None)

    def test_workspace_from_url_tempdir(self):
        self.resolver.workspace_from_url(
            mets_basename='foo.xml',
            mets_url='https://raw.githubusercontent.com/OCR-D/assets/master/data/kant_aufklaerung_1784/data/mets.xml')

    def test_workspace_from_url_download(self):
        with TemporaryDirectory() as dst_dir:
            self.resolver.workspace_from_url(
                mets_basename='foo.xml',
                dst_dir=dst_dir,
                download=True,
                mets_url='https://raw.githubusercontent.com/OCR-D/assets/master/data/kant_aufklaerung_1784/data/mets.xml')

    def test_workspace_from_url_no_clobber(self):
        with self.assertRaisesRegex(Exception, "already exists but clobber_mets is false"):
            with TemporaryDirectory() as dst_dir:
                with open(join(dst_dir, 'mets.xml'), 'w') as f:
                    f.write('CONTENT')
                self.resolver.workspace_from_url(
                    dst_dir=dst_dir,
                    mets_url='https://raw.githubusercontent.com/OCR-D/assets/master/data/kant_aufklaerung_1784/data/mets.xml')

    def test_workspace_from_url_404(self):
        with self.assertRaisesRegex(Exception, "Not found"):
            self.resolver.workspace_from_url(mets_url='https://raw.githubusercontent.com/OCR-D/assets/master/data/kant_aufklaerung_1784/data/mets.xmlX')

    def test_workspace_from_url_rel_dir(self):
        with TemporaryDirectory() as dst_dir:
            with pushd_popd(FOLDER_KANT):
                self.resolver.workspace_from_url(None, baseurl='data', dst_dir='../../../../../../../../../../../../../../../../'+dst_dir[1:])

    def test_workspace_from_url(self):
        workspace = self.resolver.workspace_from_url(METS_HEROLD)
        #  print(METS_HEROLD)
        #  print(workspace.mets)
        input_files = workspace.mets.find_files(fileGrp='OCR-D-IMG')
        #  print [str(f) for f in input_files]
        image_file = input_files[0]
        #  print(image_file)
        f = workspace.download_file(image_file)
        self.assertEqual(f.ID, 'FILE_0001_IMAGE')
        self.assertEqual(f.local_filename, 'OCR-D-IMG/FILE_0001_IMAGE')
        #  print(f)

    # pylint: disable=protected-access
    def test_resolve_image(self):
        workspace = self.resolver.workspace_from_url(METS_HEROLD)
        input_files = workspace.mets.find_files(fileGrp='OCR-D-IMG')
        f = input_files[0]
        print(f.url)
        img_pil1 = workspace._resolve_image_as_pil(f.url)
        self.assertEqual(img_pil1.size, (2875, 3749))
        img_pil2 = workspace._resolve_image_as_pil(f.url, [[0, 0], [1, 1]])
        self.assertEqual(img_pil2.size, (1, 1))
        img_pil2 = workspace._resolve_image_as_pil(f.url, [[0, 0], [1, 1]])

    # pylint: disable=protected-access
    def test_resolve_image_grayscale(self):
        img_url = assets.url_of('kant_aufklaerung_1784-binarized/data/OCR-D-IMG-NRM/OCR-D-IMG-NRM_0017')
        workspace = self.resolver.workspace_from_url(METS_HEROLD)
        img_pil1 = workspace._resolve_image_as_pil(img_url)
        self.assertEqual(img_pil1.size, (1457, 2083))
        img_pil2 = workspace._resolve_image_as_pil(img_url, [[0, 0], [1, 1]])
        self.assertEqual(img_pil2.size, (1, 1))

    # pylint: disable=protected-access
    def test_resolve_image_bitonal(self):
        img_url = assets.url_of('kant_aufklaerung_1784-binarized/data/OCR-D-IMG-1BIT/OCR-D-IMG-1BIT_0017')
        workspace = self.resolver.workspace_from_url(METS_HEROLD)
        img_pil1 = workspace._resolve_image_as_pil(img_url)
        self.assertEqual(img_pil1.size, (1457, 2083))
        img_pil2 = workspace._resolve_image_as_pil(img_url, [[0, 0], [1, 1]])
        self.assertEqual(img_pil2.size, (1, 1))

    def test_workspace_from_nothing(self):
        ws1 = self.resolver.workspace_from_nothing(None)
        self.assertIsNotNone(ws1.mets)

    def test_workspace_from_nothing_makedirs(self):
        with TemporaryDirectory() as tempdir:
            non_existant_dir = join(tempdir, 'target')
            ws1 = self.resolver.workspace_from_nothing(non_existant_dir)
            self.assertEqual(ws1.directory, non_existant_dir)

    def test_workspace_from_nothing_noclobber(self):
        with TemporaryDirectory() as tempdir:
            ws2 = self.resolver.workspace_from_nothing(tempdir)
            self.assertEqual(ws2.directory, tempdir)
            with self.assertRaisesRegex(Exception, "Not clobbering existing mets.xml in '%s'." % tempdir):
                # must fail because tempdir was just created
                self.resolver.workspace_from_nothing(tempdir)

    def test_download_to_directory_badargs_url(self):
        with self.assertRaisesRegex(Exception, "'url' must be a string"):
            self.resolver.download_to_directory(None, None)

    def test_download_to_directory_badargs_directory(self):
        with self.assertRaisesRegex(Exception, "'directory' must be a string"):
            self.resolver.download_to_directory(None, 'foo')

    def test_download_to_directory_default(self):
        with copy_of_directory(FOLDER_KANT) as dst:
            dst_subdir = join(dst, 'target')
            fn = self.resolver.download_to_directory(dst_subdir, 'file://' + join(dst, 'data/mets.xml'))
            self.assertEqual(fn, join(dst_subdir, 'file%s.data.mets.xml' % sub(r'[/_\.\-]', '.', dst)))

    def test_download_to_directory_basename(self):
        with copy_of_directory(FOLDER_KANT) as dst:
            dst_subdir = join(dst, 'target')
            fn = self.resolver.download_to_directory(dst_subdir, 'file://' + join(dst, 'data/mets.xml'), basename='foo')
            self.assertEqual(fn, join(dst_subdir, 'foo'))

    def test_download_to_directory_subdir(self):
        with copy_of_directory(FOLDER_KANT) as dst:
            dst_subdir = join(dst, 'target')
            fn = self.resolver.download_to_directory(dst_subdir, 'file://' + join(dst, 'data/mets.xml'), subdir='baz')
            self.assertEqual(fn, join(dst_subdir, 'baz', 'mets.xml'))

if __name__ == '__main__':
    main()
