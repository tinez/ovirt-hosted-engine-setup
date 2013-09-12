#
# ovirt-hosted-engine-setup -- ovirt hosted engine setup
# Copyright (C) 2013 Red Hat, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#


"""
VM configuration plugin.
"""


import uuid
import gettext


from otopi import util
from otopi import plugin
from otopi import transaction
from otopi import filetransaction
from otopi import constants as otopicons


from ovirt_hosted_engine_setup import constants as ohostedcons
from ovirt_hosted_engine_setup import util as ohostedutil


_ = lambda m: gettext.dgettext(message=m, domain='ovirt-hosted-engine-setup')


@util.export
class Plugin(plugin.PluginBase):
    """
    VM configuration plugin.
    """

    BOOT_DEVICE = {
        'cdrom': 'd',
        'pxe': 'n',
        'disk': 'c',
    }

    def __init__(self, context):
        super(Plugin, self).__init__(context=context)
        self.vdsClient = util.loadModule(
            path=ohostedcons.FileLocations.VDS_CLIENT_DIR,
            name='vdsClient'
        )

    @plugin.event(
        stage=plugin.Stages.STAGE_INIT,
    )
    def _init(self):
        self.environment.setdefault(
            ohostedcons.VMEnv.VM_UUID,
            str(uuid.uuid4())
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.MAC_ADDR,
            ohostedutil.randomMAC()
        )
        self.environment.setdefault(
            ohostedcons.VMEnv.BOOT,
            None,
        )
        self.environment[ohostedcons.VMEnv.SUBST] = {}

    @plugin.event(
        stage=plugin.Stages.STAGE_CUSTOMIZATION,
        name=ohostedcons.Stages.CONFIG_BOOT_DEVICE,
        after=(
            ohostedcons.Stages.DIALOG_TITLES_S_VM,
        ),
        before=(
            ohostedcons.Stages.DIALOG_TITLES_E_VM,
        ),
    )
    def _customization(self):
        if self.environment[ohostedcons.CoreEnv.IS_ADDITIONAL_HOST]:
            # VM has been installed, will boot from disk.
            self.environment[ohostedcons.VMEnv.BOOT] = 'disk'
            self.environment[ohostedcons.VMEnv.CDROM] = None
            self.environment[ohostedcons.VMEnv.OVF] = None
        else:
            interactive = self.environment[
                ohostedcons.VMEnv.BOOT
            ] is None
            valid = False
            while not valid:
                if interactive:
                    self.environment[
                        ohostedcons.VMEnv.BOOT
                    ] = self.dialog.queryString(
                        name='OVEHOSTED_VMENV_BOOT',
                        note=_(
                            'Please specify the device to boot the VM '
                            'from (@VALUES@) [@DEFAULT@]: '
                        ),
                        prompt=True,
                        caseSensitive=True,
                        validValues=list(self.BOOT_DEVICE.keys()),
                        default=ohostedcons.Defaults.DEFAULT_BOOT,
                    )

                if self.environment[
                    ohostedcons.VMEnv.BOOT
                ] in self.BOOT_DEVICE.keys():
                    valid = True
                elif interactive:
                    self.logger.error(
                        _(
                            'The provided boot type is not supported. '
                            'Please try again'
                        )
                    )
                else:
                    raise RuntimeError(
                        _(
                            'The provided boot type is not supported. '
                            'Please try again'
                        )
                    )

    @plugin.event(
        stage=plugin.Stages.STAGE_MISC,
        name=ohostedcons.Stages.VM_CONFIGURED,
        after=(
            ohostedcons.Stages.VM_IMAGE_AVAILABLE,
            ohostedcons.Stages.BRIDGE_AVAILABLE,
            ohostedcons.Stages.STORAGE_POOL_DISCONNECTED,
        ),
    )
    def _misc(self):
        self.logger.info(_('Configuring VM'))
        subst = {
            '@SP_UUID@': self.vdsClient.BLANK_UUID,
            '@SD_UUID@': self.environment[
                ohostedcons.StorageEnv.SD_UUID
            ],
            '@VOL_UUID@': self.environment[
                ohostedcons.StorageEnv.VOL_UUID
            ],
            '@IMG_UUID@': self.environment[
                ohostedcons.StorageEnv.IMG_UUID
            ],
            '@VM_UUID@': self.environment[
                ohostedcons.VMEnv.VM_UUID
            ],
            '@MEM_SIZE@': self.environment[
                ohostedcons.VMEnv.MEM_SIZE_MB
            ],
            '@MAC_ADDR@': self.environment[
                ohostedcons.VMEnv.MAC_ADDR
            ],
            '@NAME@': ohostedcons.Const.HOSTED_ENGINE_VM_NAME,
            '@CONSOLE_TYPE@': self.environment[
                ohostedcons.VMEnv.CONSOLE_TYPE
            ],
            '@VCPUS@': self.environment[
                ohostedcons.VMEnv.VCPUS
            ],
            '@CPU_TYPE@': self.environment[
                ohostedcons.VDSMEnv.VDSM_CPU
            ].replace('model_', ''),
            '@EMULATED_MACHINE@': self.environment[
                ohostedcons.VMEnv.EMULATED_MACHINE
            ]
        }

        if self.environment[
            ohostedcons.VMEnv.BOOT
        ] in self.BOOT_DEVICE.keys():
            subst['@BOOT@'] = self.BOOT_DEVICE[
                self.environment[ohostedcons.VMEnv.BOOT]
            ]

        if self.environment[
            ohostedcons.VMEnv.CDROM
        ] is not None:
            subst['@CDROM@'] = 'cdrom={cdrom}'.format(
                cdrom=self.environment[
                    ohostedcons.VMEnv.CDROM
                ]
            )
        else:
            subst['@CDROM@'] = ''

        content = ohostedutil.processTemplate(
            template=ohostedcons.FileLocations.ENGINE_VM_TEMPLATE,
            subst=subst,
        )
        self.environment[ohostedcons.VMEnv.SUBST] = subst
        with transaction.Transaction() as localtransaction:
            localtransaction.append(
                filetransaction.FileTransaction(
                    name=ohostedcons.FileLocations.ENGINE_VM_CONF,
                    content=content,
                    modifiedList=self.environment[
                        otopicons.CoreEnv.MODIFIED_FILES
                    ],
                ),
            )


# vim: expandtab tabstop=4 shiftwidth=4
