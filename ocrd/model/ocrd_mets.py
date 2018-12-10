from datetime import datetime

from ocrd.constants import (
    NAMESPACES as NS,
    TAG_METS_AGENT,
    TAG_METS_DIV,
    TAG_METS_FILE,
    TAG_METS_FILEGRP,
    TAG_METS_FILESEC,
    TAG_METS_FPTR,
    TAG_METS_METSHDR,
    TAG_METS_STRUCTMAP,
    IDENTIFIER_PRIORITY,
    TAG_MODS_IDENTIFIER,
    METS_XML_EMPTY,
    VERSION
)

from .ocrd_xml_base import OcrdXmlDocument, ET
from .ocrd_file import OcrdFile
from .ocrd_agent import OcrdAgent

class OcrdMets(OcrdXmlDocument):

    @staticmethod
    def empty_mets():
        tpl = METS_XML_EMPTY.decode('utf-8')
        tpl = tpl.replace('{{ VERSION }}', VERSION)
        tpl = tpl.replace('{{ NOW }}', '%s' % datetime.now())
        return OcrdMets(content=tpl.encode('utf-8'))

    def __init__(self, file_by_id=None, baseurl='', **kwargs):
        """

        Arguments:
            file_by_id (dict): Cache mapping file ID to OcrdFile
            baseurl (string, ''): Base URL to prepend to relative file URL
        """
        super(OcrdMets, self).__init__(**kwargs)
        if file_by_id is None:
            file_by_id = {}
        self._file_by_id = file_by_id
        self.baseurl = baseurl

    def __str__(self):
        return 'OcrdMets[fileGrps=%s,files=%s]' % (self.file_groups, self.find_files())

    @property
    def unique_identifier(self):
        for t in IDENTIFIER_PRIORITY:
            found = self._tree.getroot().find('.//mods:identifier[@type="%s"]' % t, NS)
            if found is not None:
                return found.text

    @unique_identifier.setter
    def unique_identifier(self, purl):
        for t in IDENTIFIER_PRIORITY:
            id_el = self._tree.getroot().find('.//mods:identifier[@type="%s"]' % t, NS)
            break
        if id_el is None:
            mods = self._tree.getroot().find('.//mods:mods', NS)
            id_el = ET.SubElement(mods, TAG_MODS_IDENTIFIER)
            id_el.set('type', 'purl')
        id_el.text = purl

    @property
    def agents(self):
        return [OcrdAgent(el_agent) for el_agent in self._tree.getroot().findall('mets:metsHdr/mets:agent', NS)]

    def add_agent(self, *args, **kwargs):
        """
        Add an agent to the list of agents in the metsHdr.
        """
        el_metsHdr = self._tree.getroot().find('.//mets:metsHdr', NS)
        if el_metsHdr is None:
            el_metsHdr = ET.Element(TAG_METS_METSHDR)
            self._tree.getroot().insert(0, el_metsHdr)
        #  assert(el_metsHdr is not None)
        el_agent = ET.SubElement(el_metsHdr, TAG_METS_AGENT)
        #  print(ET.tostring(el_metsHdr))
        return OcrdAgent(el_agent, *args, **kwargs)

    @property
    def file_groups(self):
        return [el.get('USE') for el in self._tree.getroot().findall('.//mets:fileGrp', NS)]

    def find_files(self, ID=None, fileGrp=None, pageId=None, mimetype=None, local_only=False):
        """
        List files.

        Args:
            ID (string) : ID of the file
            fileGrp (string) : USE of the fileGrp to list files of
            pageId (string) : ID of physical page manifested by matching files
            mimetype (string) : MIMETYPE of matching files
            local (boolean) : Whether to restrict results to local files, i.e. file://-URL

        Return:
            List of files.
        """
        ret = []
        fileGrp_clause = '' if fileGrp is None else '[@USE="%s"]' % fileGrp
        file_clause = ''
        if ID is not None:
            file_clause += '[@ID="%s"]' % ID
        if mimetype is not None:
            file_clause += '[@MIMETYPE="%s"]' % mimetype
        # TODO lxml says invalid predicate. I disagree
        #  if local_only:
        #      file_clause += "[mets:FLocat[starts-with(@xlink:href, 'file://')]]"

        # Search
        file_ids = self._tree.getroot().xpath("//mets:fileGrp%s/mets:file%s/@ID" % (fileGrp_clause, file_clause), namespaces=NS)
        if pageId is not None:
            by_pageid = self._tree.getroot().xpath('//mets:div[@TYPE="page"][@ID="%s"]/mets:fptr/@FILEID' % pageId, namespaces=NS)
            if by_pageid:
                file_ids = [i for i in by_pageid if i in file_ids]

        # instantiate / get from cache
        for file_id in file_ids:
            el = self._tree.getroot().find('.//mets:file[@ID="%s"]' % file_id, NS)
            if file_id not in self._file_by_id:
                self._file_by_id[file_id] = OcrdFile(el, baseurl=self.baseurl, mets=self)
            if local_only:
                url = el.find('mets:FLocat', NS).get('{%s}href' % NS['xlink'])
                if not (url.startswith('file://') or '://' not in url):
                    continue
            ret.append(self._file_by_id[file_id])
        return ret

    def add_file_group(self, fileGrp):
        el_fileSec = self._tree.getroot().find('mets:fileSec', NS)
        if el_fileSec is None:
            el_fileSec = ET.SubElement(self._tree.getroot(), TAG_METS_FILESEC)
        el_fileGrp = el_fileSec.find('mets:fileGrp[USE="%s"]' % fileGrp, NS)
        if el_fileGrp is None:
            el_fileGrp = ET.SubElement(el_fileSec, TAG_METS_FILEGRP)
            el_fileGrp.set('USE', fileGrp)
        return el_fileGrp

    def add_file(self, fileGrp, mimetype=None, url=None, ID=None, pageId=None, force=False, local_filename=None):
        if not ID:
            raise Exception("Must set ID of the mets:file")
        el_fileGrp = self._tree.getroot().find(".//mets:fileGrp[@USE='%s']" % (fileGrp), NS)
        if el_fileGrp is None:
            el_fileGrp = self.add_file_group(fileGrp)
        if ID is not None and self.find_files(ID=ID) != []:
            if not force:
                raise Exception("File with ID='%s' already exists" % ID)
            mets_file = self.find_files(ID=ID)[0]
        else:
            mets_file = OcrdFile(ET.SubElement(el_fileGrp, TAG_METS_FILE), mets=self)
        mets_file.url = url
        mets_file.mimetype = mimetype
        mets_file.ID = ID
        mets_file.pageId = pageId
        mets_file.local_filename = local_filename
        return mets_file

    @property
    def physical_pages(self):
        """
        List all page IDs
        """
        return self._tree.getroot().xpath(
            'mets:structMap[@TYPE="PHYSICAL"]/mets:div[@TYPE="physSequence"]/mets:div[@TYPE="page"]/@ID',
            namespaces=NS)

    def set_physical_page_for_file(self, pageId, ocrd_file, order=None, orderlabel=None):
        """
        Create a new physical page
        """
        #  print(pageId, ocrd_file)
        # delete any page mapping for this file.ID
        for el_fptr in self._tree.getroot().findall(
                'mets:structMap[@TYPE="PHYSICAL"]/mets:div[@TYPE="physSequence"]/mets:div[@TYPE="page"]/mets:fptr[@FILEID="%s"]' %
                ocrd_file.ID, namespaces=NS):
            el_fptr.getparent().remove(el_fptr)

        # find/construct as necessary
        el_structmap = self._tree.getroot().find('mets:structMap[@TYPE="PHYSICAL"]', NS)
        if el_structmap is None:
            el_structmap = ET.SubElement(self._tree.getroot(), TAG_METS_STRUCTMAP)
            el_structmap.set('TYPE', 'PHYSICAL')
        el_seqdiv = el_structmap.find('mets:div[@TYPE="physSequence"]', NS)
        if el_seqdiv is None:
            el_seqdiv = ET.SubElement(el_structmap, TAG_METS_DIV)
            el_seqdiv.set('TYPE', 'physSequence')
        el_pagediv = el_seqdiv.find('mets:div[@ID="%s"]' % pageId, NS)
        if el_pagediv is None:
            el_pagediv = ET.SubElement(el_seqdiv, TAG_METS_DIV)
            el_pagediv.set('TYPE', 'page')
            el_pagediv.set('ID', pageId)
            if order:
                el_pagediv.set('ORDER', order)
            if orderlabel:
                el_pagediv.set('ORDERLABEL', orderlabel)
        el_fptr = el_pagediv.find('mets:fptr[@FILEID="%s"]' % ocrd_file.ID, NS)
        if not el_fptr:
            el_fptr = ET.SubElement(el_pagediv, TAG_METS_FPTR)
            el_fptr.set('FILEID', ocrd_file.ID)

    def get_physical_page_for_file(self, ocrd_file):
        """
        Get the pageId for a ocrd_file
        """
        ret = self._tree.getroot().xpath(
            '/mets:mets/mets:structMap[@TYPE="PHYSICAL"]/mets:div[@TYPE="physSequence"]/mets:div[@TYPE="page"][./mets:fptr[@FILEID="%s"]]/@ID' %
            ocrd_file.ID, namespaces=NS)
        if ret:
            return ret[0]
