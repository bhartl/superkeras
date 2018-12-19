class LayerStack:
    """
    Represent keras layers. Can be called on a tensor to get the output after passing through the stack.
    The input must be list of layers or a keras Model instance.
    Sequential is also a keras Model, so you can pass it as the input.

    # Example
        >>> stack = LayerStack([Dense(10), Dense(20)])
        >>> stack(input_tensor)
        <tf.Tensor 'dense_2/BiasAdd:0' shape=(?, 20) dtype=float32>

        Or in the case you have keras Model instance (encoder):
        >>> stack = LayerStack(encoder)
        >>> stack(input_tensor)
        <tf.Tensor 'hidden_5_7/BiasAdd:0' shape=(?, 50) dtype=float32>
    """

    def __init__(self, keras_layers):
        try:
            keras_layers = keras_layers.layers
        except:
            pass
        if not isinstance(keras_layers, list):
            raise ValueError("`keras_layers` must be a list or a keras Model instance.")
        self.layers = keras_layers

    def __call__(self, tensor):
        return call_layers(self.layers, tensor)


def repeat_layers(layer_class, *args, name=None, name_start_index=1, **kwargs):
    """
    Instantiate layer instances from `layer_class` and return them as a list.
    The number of layers is inferred from the length of the first positional argument.
    Each positional argument must be a list. Each element inside the list will be fed to one layer instance.
    All layer instance shares the same keyword arguments.

    # Arguments
        args: Arguments must be list of positional arguments to feed to layer_class()

    # Keyword Arguments
        input_shape: Will be fed only to the first layer. This allows you to call Sequential() on the output of this function.
        name: Will be appended with suffix index to differentiate each layer from one another.
        name_start_index: If you define the name, this value will determine the starting suffix index.

    # Example
        Create a list of 2 Dense layers, with 10 units, and 20 units consecutively.
        >>> repeat_layers(Dense, [10, 20], activation='relu')
        [<keras.layers.core.Dense at 0x1d5054b5e48>,
         <keras.layers.core.Dense at 0x1d5054b5f60>]

        Create a list of 2 Conv2D layers, and checking its kernel_size.
        >>> [layer.kernel_size for layer in repeat_layers(Conv2D, [32, 64], [(3, 7), 5])]
        [(3, 7), (5, 5)]

        Create a list of 2 LSTM layers with input_shape, then feed it to Sequential() model.
        >>> layers = repeat_layers(LSTM, [1, 2], return_sequences=True, input_shape=(3, 4), name='rnn')
        >>> Sequential(layers).summary()
        _________________________________________________________________
        Layer (type)                 Output Shape              Param #   
        =================================================================
        rnn_1 (LSTM)                 (None, 3, 1)              24        
        _________________________________________________________________
        rnn_2 (LSTM)                 (None, 3, 2)              32        
        =================================================================
        Total params: 56
        Trainable params: 56
        Non-trainable params: 0
        _________________________________________________________________

    # Returns
        A list of layer instances
    """
    layers = []
    if not args:
        return [layer_class(name=name, **kwargs)]
    for i in range(len(args[0])):
        arg = []
        for j in range(len(args)):
            arg.append(args[j][i])
        if name:
            kwargs["name"] = name + "_" + str(name_start_index + i)
        layers.append(layer_class(*arg, **kwargs))
        kwargs.pop("input_shape", None)  # remove input_shape for later layers
    return layers


def call_layers(layers, tensor):
    """
    Pass `tensor` through each layer sequentially until it reaches the last layer.
    The output tensor of the last layer will be returned.
    
    This function is useful when you don't want to create a Sequential() model just to call the layers.
    One usage is for inspecting the summary() of the model which has many nested Sequential() model inside.
    Usually, if you create an inner Sequential() model, and you use it on the outer model, when you call
    summary() on the outer model, you will not see the inside of the Sequential() model.
    This function can help you expand the layers of the Sequential() model so that you can see all layers
    under the nested models.
    To see what I mean, please see the example below.
    
    # Arguments
        layers: A list of keras layers
        tensor: Input tensor to feed to the first layer
    
    # Returns
        Output tensor from the last layer.
        
    # Example
        Create some Dense layers and call them on an input tensor.
        >>> a = Input(shape=(10,), name='input')
        >>> dense_stack = repeat_layers(Dense, [16, 32, 64], name='hidden')
        >>> b = call_layers(dense_stack, a)
        >>> b
        <tf.Tensor 'hidden_3_1/BiasAdd:0' shape=(?, 64) dtype=float32>
        >>> Model(a, b).summary()
        _________________________________________________________________
        Layer (type)                 Output Shape              Param #   
        =================================================================
        input (InputLayer)           (None, 10)                0         
        _________________________________________________________________
        hidden_1 (Dense)             (None, 16)                176       
        _________________________________________________________________
        hidden_2 (Dense)             (None, 32)                544       
        _________________________________________________________________
        hidden_3 (Dense)             (None, 64)                2112      
        =================================================================
        Total params: 2,832
        Trainable params: 2,832
        Non-trainable params: 0
        _________________________________________________________________
        

        Suppose we have an encoder model in the form of Sequential() like this:
        >>> dense_stack = repeat_layers(Dense, [10, 20, 30, 40, 50], activation='relu', name='hidden', input_shape=(10,))
        >>> encoder = Sequential(dense_stack)
        
        And we also have a bigger model which uses the encoder twice on 2 inputs:
        >>> a = Input(shape=(10,))
        >>> b = Input(shape=(10,))
        
        We encode the inputs and concatenate the them. And then we create a output layer.
        We then create a model out of it.
        >>> encoding = concatenate([encoder(a), encoder(b)])
        >>> out = Dense(5)(encoding)
        >>> big_model = Model(inputs=[a, b], output=out)
        
        Let us check the summary of the model to see what it is like.
        >>> big_model.summary()
        __________________________________________________________________________________________________
        Layer (type)                    Output Shape         Param #     Connected to                     
        ==================================================================================================
        input_14 (InputLayer)           (None, 10)           0                                            
        __________________________________________________________________________________________________
        input_15 (InputLayer)           (None, 10)           0                                            
        __________________________________________________________________________________________________
        sequential_32 (Sequential)      (None, 50)           4250        input_14[0][0]                   
                                                                         input_15[0][0]                   
        __________________________________________________________________________________________________
        concatenate_2 (Concatenate)     (None, 100)          0           sequential_32[3][0]              
                                                                         sequential_32[4][0]              
        __________________________________________________________________________________________________
        dense_6 (Dense)                 (None, 5)            505         concatenate_2[0][0]              
        ==================================================================================================
        Total params: 4,755
        Trainable params: 4,755
        Non-trainable params: 0
        
        You see that the Sequential model hides all the detail. It only shows the parameter counts but it doesn't show its internal layers.
        To make it shows the internal layers, we can use `call_layers(encoder.layers, a)` instead of `encoder(a)` to expand the encoder like this:
        >>> encoding = concatenate([call_layers(encoder.layers, a), call_layers(encoder.layers, b)])
        >>> out = Dense(5)(encoding)
        >>> big_model = Model(inputs=[a, b], output=out)
        >>> big_model.summary()
        __________________________________________________________________________________________________
        Layer (type)                    Output Shape         Param #     Connected to                     
        ==================================================================================================
        input_14 (InputLayer)           (None, 10)           0                                            
        __________________________________________________________________________________________________
        input_15 (InputLayer)           (None, 10)           0                                            
        __________________________________________________________________________________________________
        hidden_1 (Dense)                (None, 10)           110         input_14[0][0]                   
                                                                         input_15[0][0]                   
        __________________________________________________________________________________________________
        hidden_2 (Dense)                (None, 20)           220         hidden_1[2][0]                   
                                                                         hidden_1[3][0]                   
        __________________________________________________________________________________________________
        hidden_3 (Dense)                (None, 30)           630         hidden_2[2][0]                   
                                                                         hidden_2[3][0]                   
        __________________________________________________________________________________________________
        hidden_4 (Dense)                (None, 40)           1240        hidden_3[2][0]                   
                                                                         hidden_3[3][0]                   
        __________________________________________________________________________________________________
        hidden_5 (Dense)                (None, 50)           2050        hidden_4[2][0]                   
                                                                         hidden_4[3][0]                   
        __________________________________________________________________________________________________
        concatenate_4 (Concatenate)     (None, 100)          0           hidden_5[2][0]                   
                                                                         hidden_5[3][0]                   
        __________________________________________________________________________________________________
        dense_8 (Dense)                 (None, 5)            505         concatenate_4[0][0]              
        ==================================================================================================
        Total params: 4,755
        Trainable params: 4,755
        Non-trainable params: 0
        __________________________________________________________________________________________________
        
        Now, you see the detail of each internal layer making up the encoder with one summary() call!

    """
    for layer in layers:
        tensor = layer(tensor)
    return tensor
