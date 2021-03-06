# Copyright 2019 Doyoung Gwak (tucan.dev@gmail.com)
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ======================
#-*- coding: utf-8 -*-

import tensorflow as tf
from tensorflow.keras import models, layers
from network_base import max_pool, upsample, inverted_bottleneck, separable_conv, convb, is_trainable

N_KPOINTS = 14
STAGE_NUM = 4

out_channel_ratio = lambda d: int(d * 1.0)
up_channel_ratio = lambda d: int(d * 1.0)

l2s = []

class HourglassModelBuilder():

    def __init__(self):
        self.build_model()


    def build_model(self):
        inputs = tf.keras.Input(shape=(256, 256, 3))  # Returns a placeholder tensor

        predictions, l2s = self.build_network(inputs, trainable=True)

        self.model = tf.keras.Model(inputs=inputs, outputs=predictions)



    def hourglass_module(self, inp, stage_nums):
        if stage_nums > 0:
            down_sample = max_pool(inp, 2, 2, 2, 2, name="hourglass_downsample_%d" % stage_nums)

            tower = inverted_bottleneck(down_sample, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            block_front = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)

            # block_front = slim.stack(down_sample, inverted_bottleneck,
            #                          [
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                          ], scope="hourglass_front_%d" % stage_nums)
            stage_nums -= 1
            block_mid = self.hourglass_module(block_front, stage_nums)
            block_back = inverted_bottleneck(
                block_mid, up_channel_ratio(6), N_KPOINTS,
                0, 3, scope="hourglass_back_%d" % stage_nums)

            up_sample = upsample(block_back, 2, "hourglass_upsample_%d" % stage_nums)

            # jump layer
            # branch_jump = slim.stack(inp, inverted_bottleneck,
            #                          [
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
            #                              (up_channel_ratio(6), N_KPOINTS, 0, 3),
            #                          ], scope="hourglass_branch_jump_%d" % stage_nums)

            tower = inverted_bottleneck(inp, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
            branch_jump = inverted_bottleneck(tower, up_channel_ratio(6), N_KPOINTS, 0, 3)

            # curr_hg_out = tf.add(up_sample, branch_jump, name="hourglass_out_%d" % stage_nums)
            curr_hg_out = layers.Add()([up_sample, branch_jump])

            # mid supervise
            l2s.append(curr_hg_out)

            return curr_hg_out

        _ = inverted_bottleneck(
            inp, up_channel_ratio(6), out_channel_ratio(24),
            0, 3, scope="hourglass_mid_%d" % stage_nums
        )
        return _

    def build_network(self, input, trainable):
        is_trainable(trainable)

        tower = convb(input, 3, 3, out_channel_ratio(16), 2, name="Conv2d_0")

        # 128, 112
        # net = slim.stack(net, inverted_bottleneck,
        #                  [
        #                      (1, out_channel_ratio(16), 0, 3),
        #                      (1, out_channel_ratio(16), 0, 3)
        #                  ], scope="Conv2d_1")
        tower = inverted_bottleneck(tower, 1, out_channel_ratio(16), 0, 3)
        tower = inverted_bottleneck(tower, 1, out_channel_ratio(16), 0, 3)

        # 64, 56
        # net = slim.stack(net, inverted_bottleneck,
        #                  [
        #                      (up_channel_ratio(6), out_channel_ratio(24), 1, 3),
        #                      (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
        #                      (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
        #                      (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
        #                      (up_channel_ratio(6), out_channel_ratio(24), 0, 3),
        #                  ], scope="Conv2d_2")
        tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 1, 3)
        tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
        tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
        tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)
        tower = inverted_bottleneck(tower, up_channel_ratio(6), out_channel_ratio(24), 0, 3)

        net_h_w = int(tower.shape[1])
        # build network recursively
        hg_out = self.hourglass_module(tower, STAGE_NUM)

        for index, l2 in enumerate(l2s):
            l2_w_h = int(l2.shape[1])
            if l2_w_h == net_h_w:
                continue
            scale = net_h_w // l2_w_h
            l2s[index] = upsample(l2, scale, name="upsample_for_loss_%d" % index)

        return hg_out, l2s

