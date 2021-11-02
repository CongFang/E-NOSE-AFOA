from keras.layers import GlobalAveragePooling1D, GlobalMaxPooling1D, Reshape, Dense, multiply, Permute, Concatenate, Conv1D, Add, Activation, Lambda
from keras import backend as K
from keras.activations import sigmoid
from keras import initializers
import pdb

def attach_attention_module(net, attention_module, cbam_mode):
  if attention_module == 'se_block': # SE_block
    net = se_block(net)
  elif attention_module == 'cbam_block': # CBAM_block
    net = cbam_block(net, mode=cbam_mode)
  else:
    raise Exception("'{}' is not supported attention module!".format(attention_module))

  return net

def se_block(input_feature, ratio=8):
	"""Contains the implementation of Squeeze-and-Excitation(SE) block.
	As described in https://arxiv.org/abs/1709.01507.
	"""
	
	channel_axis = 1 if K.image_data_format() == "channels_first" else -1
	channel = input_feature._keras_shape[channel_axis]

	se_feature = GlobalAveragePooling1D()(input_feature)
	se_feature = Reshape((1, channel))(se_feature)
	assert se_feature._keras_shape[1:] == (1,channel)
	se_feature = Dense(channel // ratio,
					   activation='relu',
					   kernel_initializer=initializers.he_normal(seed=None),
					   use_bias=True,
					   bias_initializer='zeros')(se_feature)
	assert se_feature._keras_shape[1:] == (1,channel//ratio)
	se_feature = Dense(channel,
					   activation='sigmoid',
					   kernel_initializer=initializers.he_normal(seed=None),
					   use_bias=True,
					   bias_initializer='zeros')(se_feature)
	assert se_feature._keras_shape[1:] == (1,channel)
	if K.image_data_format() == 'channels_first':
		se_feature = Permute((2, 1))(se_feature)

	se_feature = multiply([input_feature, se_feature])
	return se_feature

def cbam_block(cbam_feature, ratio=8, mode=1):
	"""Contains the implementation of Convolutional Block Attention Module(CBAM) block.
	As described in https://arxiv.org/abs/1807.06521.
	"""
	# pdb.set_trace()
	if mode ==1:
		# cbam_block_parallel mode
		channel_feature = channel_attention(cbam_feature, ratio)
		spatial_feature = spatial_attention(cbam_feature)
		cbam_feature = Add()([channel_feature,spatial_feature])
		cbam_feature = Activation('sigmoid')(cbam_feature)

	elif mode ==2:
		# cbam_block_channel_first mode
		cbam_feature = channel_attention(cbam_feature, ratio)
		cbam_feature = spatial_attention(cbam_feature)
		
	elif mode ==3:
		# cbam_block_spatial_first mode
		cbam_feature = spatial_attention(cbam_feature)
		cbam_feature = channel_attention(cbam_feature, ratio)

	elif mode ==4:
		# channel_attention_module_only mode
		cbam_feature = channel_attention(cbam_feature, ratio)

	elif mode ==5:
		# spatial_attention_module_only mode
		cbam_feature = spatial_attention(cbam_feature)

	else:
		pass

	return cbam_feature

def channel_attention(input_feature, ratio=8):
	
	channel_axis = 1 if K.image_data_format() == "channels_first" else -1
	channel = input_feature._keras_shape[channel_axis]
	
	shared_layer_one = Dense(channel//ratio,
							 activation='relu',
							 kernel_initializer=initializers.he_normal(seed=None),
							 use_bias=True,
							 bias_initializer='zeros')
	shared_layer_two = Dense(channel,
							 kernel_initializer=initializers.he_normal(seed=None),
							 use_bias=True,
							 bias_initializer='zeros')
	
	avg_pool = GlobalAveragePooling1D()(input_feature)    
	avg_pool = Reshape((1,channel))(avg_pool)
	assert avg_pool._keras_shape[1:] == (1,channel)
	avg_pool = shared_layer_one(avg_pool)
	assert avg_pool._keras_shape[1:] == (1,channel//ratio)
	avg_pool = shared_layer_two(avg_pool)
	assert avg_pool._keras_shape[1:] == (1,channel)
	
	max_pool = GlobalMaxPooling1D()(input_feature)
	max_pool = Reshape((1,channel))(max_pool)
	assert max_pool._keras_shape[1:] == (1,channel)
	max_pool = shared_layer_one(max_pool)
	assert max_pool._keras_shape[1:] == (1,channel//ratio)
	max_pool = shared_layer_two(max_pool)
	assert max_pool._keras_shape[1:] == (1,channel)
	
	cbam_feature = Add()([avg_pool,max_pool])
	cbam_feature = Activation('sigmoid')(cbam_feature)
	
	if K.image_data_format() == "channels_first":
		cbam_feature = Permute((2, 1))(cbam_feature)
	
	return multiply([input_feature, cbam_feature])

def spatial_attention(input_feature):
	kernel_size = 7
	
	if K.image_data_format() == "channels_first":
		channel = input_feature._keras_shape[1]
		cbam_feature = Permute((2,1))(input_feature)
	else:
		channel = input_feature._keras_shape[-1]
		cbam_feature = input_feature
	
	avg_pool = Lambda(lambda x: K.mean(x, axis=2, keepdims=True))(cbam_feature)
	assert avg_pool._keras_shape[-1] == 1
	max_pool = Lambda(lambda x: K.max(x, axis=2, keepdims=True))(cbam_feature)
	assert max_pool._keras_shape[-1] == 1
	concat = Concatenate(axis=2)([avg_pool, max_pool])
	assert concat._keras_shape[-1] == 2
	cbam_feature = Conv1D(filters = 1,
					kernel_size=kernel_size,
					strides=1,
					padding='same',
					activation='sigmoid',
					kernel_initializer=initializers.he_normal(seed=None),
					use_bias=False)(concat)	
	assert cbam_feature._keras_shape[-1] == 1
	
	if K.image_data_format() == "channels_first":
		cbam_feature = Permute((2, 1))(cbam_feature)
		
	return multiply([input_feature, cbam_feature])
		
	